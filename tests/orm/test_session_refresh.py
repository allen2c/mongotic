from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import NotFound, select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

test_company = f"test_{rand_str(10)}"


class User(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "user_refresh"

    name: Text = Field(...)
    company: Optional[Text] = Field(None)
    age: Optional[int] = Field(None)


@pytest.fixture(autouse=True)
def cleanup(mongo_engine: "MongoClient"):
    yield
    mongo_engine["test"]["user_refresh"].delete_many({"company": test_company})


def test_refresh_reloads_fields_from_db(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Alice", company=test_company, age=25)
        session.add(user)
        session.flush()

        # Simulate external update directly via pymongo
        mongo_engine["test"]["user_refresh"].update_one(
            {"_id": __import__("bson").ObjectId(user._id)},
            {"$set": {"age": 99}},
        )

        assert user.age == 25  # in-memory still stale
        session.refresh(user)
        assert user.age == 99  # now up-to-date


def test_refresh_clears_pending_updates(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Bob", company=test_company, age=30)
        session.add(user)
        session.flush()

        user.age = 31  # stage a pending update
        assert len(session.dirty) == 1

        session.refresh(user)
        # After refresh, pending changes for this instance should be cleared
        assert session.dirty == []


def test_refresh_raises_value_error_for_unpersisted(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Carol", company=test_company, age=35)
        # Not added/flushed → _id is None
        with pytest.raises(ValueError, match="_id is None"):
            session.refresh(user)


def test_refresh_raises_not_found_for_deleted_doc(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Dave", company=test_company, age=40)
        session.add(user)
        session.flush()

        # Delete directly from DB
        mongo_engine["test"]["user_refresh"].delete_one(
            {"_id": __import__("bson").ObjectId(user._id)}
        )

        with pytest.raises(NotFound):
            session.refresh(user)
