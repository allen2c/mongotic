"""Integration tests for .is_(None) / .is_not(None) null operators (MGT-019).

MongoDB behaviour:
  - ``{"field": {"$eq": null}}``  matches documents where field is null OR missing.
  - ``{"field": {"$ne": null}}``  matches documents where field exists and is not null.
"""

from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import and_, not_, or_, select
from mongotic.model import ModelFieldOperation, MongoBaseModel, Operator
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

_TAG = rand_str(10)


class NullUser(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "null_user"

    tag: Text = Field(...)
    name: Text = Field(...)
    email: Optional[Text] = Field(None)


# ---------------------------------------------------------------------------
# Unit tests — operator / filter shape
# ---------------------------------------------------------------------------


def test_is_none_returns_equal_operator():
    op = NullUser.email.is_(None)
    assert isinstance(op, ModelFieldOperation)
    assert op.operation == Operator.EQUAL
    assert op.value is None


def test_is_not_none_returns_not_equal_operator():
    op = NullUser.email.is_not(None)
    assert isinstance(op, ModelFieldOperation)
    assert op.operation == Operator.NOT_EQUAL
    assert op.value is None


def test_is_none_filter_shape():
    result = ModelFieldOperation.to_mongo_filter([NullUser.email.is_(None)])
    assert result == {"email": {"$eq": None}}


def test_is_not_none_filter_shape():
    result = ModelFieldOperation.to_mongo_filter([NullUser.email.is_not(None)])
    assert result == {"email": {"$ne": None}}


def test_is_none_composes_with_or():
    f = or_(NullUser.email.is_(None), NullUser.email == "fallback@example.com")
    result = f.to_mongo_filter()
    assert result == {
        "$or": [
            {"email": {"$eq": None}},
            {"email": {"$eq": "fallback@example.com"}},
        ]
    }


def test_is_not_none_composes_with_not():
    # not_(email.is_not(None)) → field-level $not on $ne
    f = not_(NullUser.email.is_not(None))
    result = f.to_mongo_filter()
    assert result == {"email": {"$not": {"$ne": None}}}


# ---------------------------------------------------------------------------
# Integration tests — real MongoDB queries
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seed_and_cleanup(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = [
        NullUser(tag=_TAG, name="alice", email="alice@example.com"),
        NullUser(tag=_TAG, name="bob", email=None),
        NullUser(tag=_TAG, name="carol", email="carol@example.com"),
    ]
    session.add_all(users)
    session.commit()

    yield

    session2 = Session()
    for u in session2.scalars(select(NullUser).where(NullUser.tag == _TAG)).all():
        session2.delete(u)
    session2.commit()


def test_is_none_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(NullUser).where(
            NullUser.tag == _TAG,
            NullUser.email.is_(None),
        )
    ).all()
    assert len(results) == 1
    assert results[0].name == "bob"


def test_is_not_none_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(NullUser).where(
            NullUser.tag == _TAG,
            NullUser.email.is_not(None),
        )
    ).all()
    assert len(results) == 2
    names = {u.name for u in results}
    assert names == {"alice", "carol"}


def test_is_none_with_or(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(NullUser).where(
            NullUser.tag == _TAG,
            or_(NullUser.email.is_(None), NullUser.email == "alice@example.com"),
        )
    ).all()
    assert len(results) == 2
    names = {u.name for u in results}
    assert names == {"alice", "bob"}


def test_is_not_none_with_and(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(NullUser).where(
            NullUser.tag == _TAG,
            and_(NullUser.email.is_not(None), NullUser.name == "alice"),
        )
    ).all()
    assert len(results) == 1
    assert results[0].name == "alice"
