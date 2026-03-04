from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

test_company = f"test_{rand_str(10)}"


class User(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "user_state"

    name: Text = Field(...)
    company: Optional[Text] = Field(None)
    age: Optional[int] = Field(None)


@pytest.fixture(autouse=True)
def cleanup(mongo_engine: "MongoClient"):
    yield
    mongo_engine["test"]["user_state"].delete_many({"company": test_company})


def test_new_reflects_staged_adds(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        assert session.new == []
        user = User(name="Alice", company=test_company, age=25)
        session.add(user)
        assert len(session.new) == 1
        assert session.new[0] is user


def test_new_empty_after_flush(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        session.add(User(name="Alice", company=test_company, age=25))
        session.flush()
        assert session.new == []


def test_dirty_reflects_field_changes(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Bob", company=test_company, age=30)
        session.add(user)
        session.flush()

        assert session.dirty == []
        user.age = 31
        dirty = session.dirty
        assert len(dirty) == 1
        assert dirty[0] is user


def test_dirty_deduplicates_multiple_field_changes(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Carol", company=test_company, age=35)
        session.add(user)
        session.flush()

        user.age = 36
        user.name = "Carol Updated"
        # Two field changes on same instance → dirty list has 1 entry
        assert len(session.dirty) == 1
        assert session.dirty[0] is user


def test_dirty_empty_after_flush(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Dave", company=test_company, age=40)
        session.add(user)
        session.flush()
        user.age = 41
        session.flush()
        assert session.dirty == []


def test_deleted_reflects_staged_deletes(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Eve", company=test_company, age=22)
        session.add(user)
        session.flush()

        assert session.deleted == []
        session.delete(user)
        assert len(session.deleted) == 1
        assert session.deleted[0] is user


def test_deleted_empty_after_flush(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Frank", company=test_company, age=28)
        session.add(user)
        session.flush()
        session.delete(user)
        session.flush()
        assert session.deleted == []


def test_state_properties_return_shallow_copies(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        user = User(name="Grace", company=test_company, age=33)
        session.add(user)

        new_copy = session.new
        new_copy.clear()  # mutating the copy should not affect session state
        assert len(session.new) == 1
