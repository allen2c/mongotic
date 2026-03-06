"""Integration tests for string operators (MGT-022):
like, ilike, contains, startswith, endswith.
"""

from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import or_, select
from mongotic.model import ModelFieldOperation, MongoBaseModel, RegexValue
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

_TAG = rand_str(10)


class StrUser(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "str_user"

    tag: Text = Field(...)
    name: Text = Field(...)
    email: Optional[Text] = Field(None)


# ---------------------------------------------------------------------------
# Unit tests — filter dict shape
# ---------------------------------------------------------------------------


def test_like_prefix_shape():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.like("Al%")])
    assert result == {"name": {"$regex": "^Al.*$"}}


def test_like_suffix_shape():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.like("%son")])
    assert result == {"name": {"$regex": "^.*son$"}}


def test_like_middle_shape():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.like("%li%")])
    assert result == {"name": {"$regex": "^.*li.*$"}}


def test_like_single_wildcard():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.like("A_ice")])
    assert result == {"name": {"$regex": "^A.ice$"}}


def test_ilike_adds_options():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.ilike("al%")])
    assert result == {"name": {"$regex": "^al.*$", "$options": "i"}}


def test_contains_escapes_special_chars():
    result = ModelFieldOperation.to_mongo_filter([StrUser.email.contains("@gmail.com")])
    assert result == {"email": {"$regex": r"@gmail\.com"}}


def test_startswith_shape():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.startswith("Al")])
    assert result == {"name": {"$regex": "^Al"}}


def test_endswith_shape():
    result = ModelFieldOperation.to_mongo_filter([StrUser.name.endswith("son")])
    assert result == {"name": {"$regex": "son$"}}


def test_string_op_composes_with_or():
    f = or_(StrUser.name.startswith("Al"), StrUser.name.startswith("Bo"))
    result = f.to_mongo_filter()
    assert result == {"$or": [{"name": {"$regex": "^Al"}}, {"name": {"$regex": "^Bo"}}]}


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seed_and_cleanup(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    session.add_all(
        [
            StrUser(tag=_TAG, name="Alice", email="alice@gmail.com"),
            StrUser(tag=_TAG, name="Bob", email="bob@yahoo.com"),
            StrUser(tag=_TAG, name="Alison", email="alison@gmail.com"),
            StrUser(tag=_TAG, name="Charlie", email="charlie@gmail.com"),
        ]
    )
    session.commit()
    yield
    session2 = Session()
    for u in session2.scalars(select(StrUser).where(StrUser.tag == _TAG)).all():
        session2.delete(u)
    session2.commit()


def test_like_prefix(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(StrUser).where(StrUser.tag == _TAG, StrUser.name.like("Al%"))
    ).all()
    assert len(results) == 2
    assert {u.name for u in results} == {"Alice", "Alison"}


def test_ilike_prefix(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(StrUser).where(StrUser.tag == _TAG, StrUser.name.ilike("al%"))
    ).all()
    assert len(results) == 2
    assert {u.name for u in results} == {"Alice", "Alison"}


def test_contains(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(StrUser).where(StrUser.tag == _TAG, StrUser.email.contains("@gmail.com"))
    ).all()
    assert len(results) == 3
    assert {u.name for u in results} == {"Alice", "Alison", "Charlie"}


def test_startswith(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(StrUser).where(StrUser.tag == _TAG, StrUser.name.startswith("Al"))
    ).all()
    assert len(results) == 2


def test_endswith(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(StrUser).where(StrUser.tag == _TAG, StrUser.name.endswith("ce"))
    ).all()
    assert len(results) == 1
    assert results[0].name == "Alice"


def test_like_no_wildcard(mongo_engine: MongoClient):
    """Exact match when pattern has no wildcards."""
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(StrUser).where(StrUser.tag == _TAG, StrUser.name.like("Bob"))
    ).all()
    assert len(results) == 1
    assert results[0].name == "Bob"
