from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.operations import IndexModel

from mongotic import create_indexes
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

test_suffix = rand_str(8)


class UserWithIndexes(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"user_idx_{test_suffix}"
    __indexes__ = [
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("created_at", DESCENDING)]),
    ]

    email: Text = Field(...)
    name: Optional[Text] = Field(None)
    created_at: Optional[int] = Field(None)


class UserNoIndexes(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"user_noidx_{test_suffix}"

    name: Text = Field(...)


@pytest.fixture(autouse=True)
def cleanup(mongo_engine: "MongoClient"):
    yield
    mongo_engine["test"][UserWithIndexes.__tablename__].drop()
    mongo_engine["test"][UserNoIndexes.__tablename__].drop()


def test_create_indexes_applies_to_collection(mongo_engine: "MongoClient"):
    create_indexes(mongo_engine, UserWithIndexes)

    index_info = mongo_engine["test"][UserWithIndexes.__tablename__].index_information()
    index_keys = [
        tuple(v["key"]) for v in index_info.values() if v["key"] != [("_id", 1)]
    ]
    assert ("email", 1) in [k[0] for k in index_keys]
    assert ("created_at", -1) in [k[0] for k in index_keys]


def test_create_indexes_unique_enforced(mongo_engine: "MongoClient"):
    from pymongo.errors import DuplicateKeyError

    create_indexes(mongo_engine, UserWithIndexes)
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        session.add(UserWithIndexes(email="alice@example.com", name="Alice"))
        session.flush()

    with Session() as session:
        session.add(UserWithIndexes(email="alice@example.com", name="Alice Duplicate"))
        with pytest.raises(DuplicateKeyError):
            session.flush()


def test_create_indexes_skips_model_without_indexes(mongo_engine: "MongoClient"):
    # Should not raise even though model has no __indexes__
    create_indexes(mongo_engine, UserNoIndexes)

    index_info = mongo_engine["test"][UserNoIndexes.__tablename__].index_information()
    # Only the default _id index should exist
    non_id_indexes = [k for k in index_info if k != "_id_"]
    assert non_id_indexes == []


def test_create_indexes_accepts_multiple_models(mongo_engine: "MongoClient"):
    # Should handle multiple model args without error
    create_indexes(mongo_engine, UserWithIndexes, UserNoIndexes)

    index_info = mongo_engine["test"][UserWithIndexes.__tablename__].index_information()
    assert len(index_info) > 1  # _id + our custom indexes


def test_indexes_class_attribute_not_instance_field(mongo_engine: "MongoClient"):
    # __indexes__ should not appear as a Pydantic model field
    user = UserWithIndexes(email="test@example.com")
    assert "indexes" not in user.model_dump()
    assert "__indexes__" not in user.model_dump()


def test_default_indexes_is_empty_list():
    # Models without explicit __indexes__ should default to []
    assert UserNoIndexes.__indexes__ == []
