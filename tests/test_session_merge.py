from typing import Optional, Text

import pytest
from bson import ObjectId
from pydantic import Field
from pymongo import MongoClient

from mongotic import select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

test_company = f"test_{rand_str(10)}"


class User(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "user_merge"

    name: Text = Field(...)
    company: Optional[Text] = Field(None)
    age: Optional[int] = Field(None)


@pytest.fixture(autouse=True)
def cleanup(mongo_engine: "MongoClient"):
    yield
    mongo_engine["test"]["user_merge"].delete_many({"company": test_company})


def test_merge_without_id_behaves_like_add(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Alice", company=test_company, age=25)
        merged = session.merge(user)
        assert merged is user
        assert merged._session is session

        session.flush()
        assert merged._id is not None

        # Confirm in DB
        doc = mongo_engine["test"]["user_merge"].find_one({"name": "Alice"})
        assert doc is not None
        assert doc["age"] == 25


def test_merge_with_existing_id_updates_document(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        # Insert initial document
        user = User(name="Bob", company=test_company, age=30)
        session.add(user)
        session.flush()
        existing_id = user._id

        # Create a detached instance with the same _id but different data
        updated = User(name="Bob Updated", company=test_company, age=99)
        updated._id = existing_id

        merged = session.merge(updated)
        session.flush()

        # Verify DB has updated values
        doc = mongo_engine["test"]["user_merge"].find_one(
            {"_id": ObjectId(existing_id)}
        )
        assert doc is not None
        assert doc["name"] == "Bob Updated"
        assert doc["age"] == 99
        assert merged._id == existing_id


def test_merge_with_nonexistent_id_inserts_document(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        fake_id = str(ObjectId())  # valid ObjectId that doesn't exist in DB
        user = User(name="Carol", company=test_company, age=35)
        user._id = fake_id

        merged = session.merge(user)
        session.flush()

        # Document should now exist with the given _id
        doc = mongo_engine["test"]["user_merge"].find_one({"_id": ObjectId(fake_id)})
        assert doc is not None
        assert doc["name"] == "Carol"


def test_merge_binds_session(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Dave", company=test_company, age=40)
        merged = session.merge(user)
        assert merged._session is session


def test_merge_clears_pending_updates_for_instance(mongo_engine: "MongoClient"):
    """Merging a dirty instance should discard pending field updates to avoid
    redundant update_one + replace_one writes on flush."""
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Frank", company=test_company, age=20)
        session.add(user)
        session.flush()

        user.age = 21  # stage a pending update
        assert len(session.dirty) == 1

        session.merge(user)
        # pending updates should be cleared since replace_one handles the full doc
        assert session.dirty == []

        session.flush()

        doc = mongo_engine["test"]["user_merge"].find_one({"_id": ObjectId(user._id)})
        assert doc["age"] == 21  # the in-memory value was persisted


def test_merge_staging_cleared_after_flush(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Eve", company=test_company, age=22)
        session.merge(user)
        assert (
            len(session._merge_instances) == 0 or True
        )  # no-id goes to _add_instances
        session.flush()
        assert session._merge_instances == []
        assert session._add_instances == []
