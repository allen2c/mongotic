"""Integration tests for .between() range operator (MGT-023)."""

from datetime import datetime, timezone
from typing import Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import and_, select
from mongotic.model import ModelFieldOperation, MongoBaseModel, Operator
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

_TAG = rand_str(10)


class RangeItem(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "range_item"

    tag: Text = Field(...)
    value: int = Field(...)
    score: float = Field(...)


# ---------------------------------------------------------------------------
# Unit tests — filter dict shape
# ---------------------------------------------------------------------------


def test_between_operator_enum():
    op = RangeItem.value.between(18, 65)
    assert op.operation == Operator.BETWEEN
    assert op.value == (18, 65)


def test_between_filter_shape():
    result = ModelFieldOperation.to_mongo_filter([RangeItem.value.between(18, 65)])
    assert result == {"value": {"$gte": 18, "$lte": 65}}


def test_between_float_shape():
    result = ModelFieldOperation.to_mongo_filter([RangeItem.score.between(1.5, 9.9)])
    assert result == {"score": {"$gte": 1.5, "$lte": 9.9}}


def test_between_with_other_condition():
    result = ModelFieldOperation.to_mongo_filter(
        [RangeItem.tag == "x", RangeItem.value.between(10, 20)]
    )
    assert result == {"tag": {"$eq": "x"}, "value": {"$gte": 10, "$lte": 20}}


def test_between_composes_with_and():
    f = and_(RangeItem.value.between(10, 50), RangeItem.score.between(1.0, 5.0))
    result = f.to_mongo_filter()
    assert result == {
        "$and": [
            {"value": {"$gte": 10, "$lte": 50}},
            {"score": {"$gte": 1.0, "$lte": 5.0}},
        ]
    }


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seed_and_cleanup(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    session.add_all(
        [
            RangeItem(tag=_TAG, value=10, score=1.0),
            RangeItem(tag=_TAG, value=25, score=5.0),
            RangeItem(tag=_TAG, value=50, score=7.5),
            RangeItem(tag=_TAG, value=80, score=9.9),
        ]
    )
    session.commit()
    yield
    session2 = Session()
    for item in session2.scalars(select(RangeItem).where(RangeItem.tag == _TAG)).all():
        session2.delete(item)
    session2.commit()


def test_between_int(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(RangeItem).where(RangeItem.tag == _TAG, RangeItem.value.between(20, 60))
    ).all()
    assert len(results) == 2
    assert {r.value for r in results} == {25, 50}


def test_between_inclusive_bounds(mongo_engine: MongoClient):
    """Bounds are inclusive — value==10 and value==80 should be included."""
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(RangeItem).where(RangeItem.tag == _TAG, RangeItem.value.between(10, 80))
    ).all()
    assert len(results) == 4


def test_between_no_match(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(RangeItem).where(RangeItem.tag == _TAG, RangeItem.value.between(30, 40))
    ).all()
    assert len(results) == 0


def test_between_float(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    results = session.scalars(
        select(RangeItem).where(
            RangeItem.tag == _TAG, RangeItem.score.between(4.0, 8.0)
        )
    ).all()
    assert len(results) == 2
    assert {r.score for r in results} == {5.0, 7.5}
