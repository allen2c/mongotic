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
    __tablename__ = "user_iter"

    name: Text = Field(...)
    company: Optional[Text] = Field(None)
    age: Optional[int] = Field(None)


@pytest.fixture(autouse=True)
def seed(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        session.add_all(
            [
                User(name="Alice", company=test_company, age=25),
                User(name="Bob", company=test_company, age=30),
                User(name="Carol", company=test_company, age=35),
            ]
        )
        session.commit()
    yield
    mongo_engine["test"]["user_iter"].delete_many({"company": test_company})


def test_iter_for_loop(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        stmt = select(User).where(User.company == test_company)
        names = []
        for user in session.scalars(stmt):
            names.append(user.name)
        assert set(names) == {"Alice", "Bob", "Carol"}


def test_iter_list_comprehension(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        stmt = select(User).where(User.company == test_company)
        names = [u.name for u in session.scalars(stmt)]
        assert set(names) == {"Alice", "Bob", "Carol"}


def test_iter_multiple_times_same_result(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        stmt = select(User).where(User.company == test_company)
        result = session.scalars(stmt)
        names_first = [u.name for u in result]
        names_second = [u.name for u in result]
        assert set(names_first) == set(names_second)


def test_iter_yields_hydrated_instances(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        stmt = select(User).where(User.company == test_company)
        for user in session.scalars(stmt):
            assert isinstance(user, User)
            assert user._id is not None
            assert user._session is session


def test_iter_coexists_with_all(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    with Session() as session:
        stmt = select(User).where(User.company == test_company)
        result = session.scalars(stmt)
        via_all = {u.name for u in result.all()}
        via_iter = {u.name for u in result}
        assert via_all == via_iter
