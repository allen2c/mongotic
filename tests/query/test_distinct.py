"""Integration tests for Select.distinct() (MGT-024)."""

from typing import Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str

_TAG = rand_str(10)


class DistUser(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "dist_user"

    tag: Text = Field(...)
    role: Text = Field(...)
    dept: Text = Field(...)


# ---------------------------------------------------------------------------
# Unit tests — Select state
# ---------------------------------------------------------------------------


def test_distinct_sets_field():
    from mongotic.query import select as select_fn

    stmt = select_fn(DistUser).distinct(DistUser.role)
    assert stmt._distinct_field is not None
    assert stmt._distinct_field.field_name == "role"


def test_distinct_is_chainable():
    stmt = select(DistUser).where(DistUser.tag == "x").distinct(DistUser.role)
    assert stmt._distinct_field.field_name == "role"
    assert len(stmt._filters) == 1


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seed_and_cleanup(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    session.add_all(
        [
            DistUser(tag=_TAG, role="admin", dept="eng"),
            DistUser(tag=_TAG, role="admin", dept="hr"),
            DistUser(tag=_TAG, role="member", dept="eng"),
            DistUser(tag=_TAG, role="guest", dept="eng"),
        ]
    )
    session.commit()
    yield
    session2 = Session()
    for u in session2.scalars(select(DistUser).where(DistUser.tag == _TAG)).all():
        session2.delete(u)
    session2.commit()


def test_distinct_all_values(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    roles = session.scalars(
        select(DistUser).where(DistUser.tag == _TAG).distinct(DistUser.role)
    ).all()
    assert sorted(roles) == ["admin", "guest", "member"]


def test_distinct_with_filter(mongo_engine: MongoClient):
    """distinct filtered by dept==eng should exclude hr admin."""
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    roles = session.scalars(
        select(DistUser)
        .where(DistUser.tag == _TAG, DistUser.dept == "eng")
        .distinct(DistUser.role)
    ).all()
    assert sorted(roles) == ["admin", "guest", "member"]


def test_distinct_single_result(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()
    depts = session.scalars(
        select(DistUser)
        .where(DistUser.tag == _TAG, DistUser.role == "guest")
        .distinct(DistUser.dept)
    ).all()
    assert depts == ["eng"]
