"""Integration tests for or_(), and_(), not_() logical combinators (MGT-018)."""

from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import and_, not_, or_, select
from mongotic.model import CompoundFilter, ModelFieldOperation, MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str, utc_now

# Unique sentinel so tests don't collide with other test runs
_TAG = rand_str(10)

ROLE_ADMIN = "admin"
ROLE_MOD = "moderator"
ROLE_GUEST = "guest"
AGE_ADULT = 30
AGE_MINOR = 15


class LogicUser(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "logic_user"

    tag: Text = Field(...)  # isolates this test run
    role: Text = Field(...)
    age: int = Field(...)


# ---------------------------------------------------------------------------
# Unit tests — filter dict shape (no DB required)
# ---------------------------------------------------------------------------


def test_or_filter_shape():
    f = or_(LogicUser.role == ROLE_ADMIN, LogicUser.role == ROLE_MOD)
    assert isinstance(f, CompoundFilter)
    result = f.to_mongo_filter()
    assert result == {
        "$or": [
            {"role": {"$eq": ROLE_ADMIN}},
            {"role": {"$eq": ROLE_MOD}},
        ]
    }


def test_and_filter_shape():
    f = and_(LogicUser.age >= AGE_ADULT, LogicUser.role == ROLE_ADMIN)
    result = f.to_mongo_filter()
    assert result == {
        "$and": [
            {"age": {"$gte": AGE_ADULT}},
            {"role": {"$eq": ROLE_ADMIN}},
        ]
    }


def test_not_single_op_shape():
    f = not_(LogicUser.role == ROLE_GUEST)
    result = f.to_mongo_filter()
    assert result == {"role": {"$not": {"$eq": ROLE_GUEST}}}


def test_not_or_produces_nor():
    f = not_(or_(LogicUser.role == ROLE_GUEST, LogicUser.role == "anonymous"))
    result = f.to_mongo_filter()
    assert result == {
        "$nor": [
            {"role": {"$eq": ROLE_GUEST}},
            {"role": {"$eq": "anonymous"}},
        ]
    }


def test_nested_and_or_shape():
    f = and_(
        or_(LogicUser.role == ROLE_ADMIN, LogicUser.role == ROLE_MOD),
        LogicUser.age >= AGE_ADULT,
    )
    result = f.to_mongo_filter()
    assert result == {
        "$and": [
            {"$or": [{"role": {"$eq": ROLE_ADMIN}}, {"role": {"$eq": ROLE_MOD}}]},
            {"age": {"$gte": AGE_ADULT}},
        ]
    }


def test_to_mongo_filter_mixed_list():
    """Implicit-AND of simple ops and a CompoundFilter at top level."""
    ops = [
        LogicUser.age >= AGE_ADULT,
        or_(LogicUser.role == ROLE_ADMIN, LogicUser.role == ROLE_MOD),
    ]
    result = ModelFieldOperation.to_mongo_filter(ops)
    assert result == {
        "age": {"$gte": AGE_ADULT},
        "$or": [{"role": {"$eq": ROLE_ADMIN}}, {"role": {"$eq": ROLE_MOD}}],
    }


# ---------------------------------------------------------------------------
# Integration tests — real MongoDB queries
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seed_and_cleanup(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = [
        LogicUser(tag=_TAG, role=ROLE_ADMIN, age=AGE_ADULT),
        LogicUser(tag=_TAG, role=ROLE_MOD, age=AGE_ADULT),
        LogicUser(tag=_TAG, role=ROLE_GUEST, age=AGE_MINOR),
    ]
    session.add_all(users)
    session.commit()

    yield

    # cleanup
    session2 = Session()
    for u in session2.scalars(select(LogicUser).where(LogicUser.tag == _TAG)).all():
        session2.delete(u)
    session2.commit()


def test_or_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(LogicUser).where(
            LogicUser.tag == _TAG,
            or_(LogicUser.role == ROLE_ADMIN, LogicUser.role == ROLE_MOD),
        )
    ).all()
    assert len(results) == 2
    roles = {u.role for u in results}
    assert roles == {ROLE_ADMIN, ROLE_MOD}


def test_and_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(LogicUser).where(
            LogicUser.tag == _TAG,
            and_(LogicUser.age >= AGE_ADULT, LogicUser.role == ROLE_ADMIN),
        )
    ).all()
    assert len(results) == 1
    assert results[0].role == ROLE_ADMIN


def test_not_single_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(LogicUser).where(
            LogicUser.tag == _TAG,
            not_(LogicUser.role == ROLE_GUEST),
        )
    ).all()
    assert len(results) == 2
    assert all(u.role != ROLE_GUEST for u in results)


def test_not_or_nor_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    # not_(or_(guest, anonymous)) should return admin + mod
    results = session.scalars(
        select(LogicUser).where(
            LogicUser.tag == _TAG,
            not_(or_(LogicUser.role == ROLE_GUEST, LogicUser.role == "anonymous")),
        )
    ).all()
    assert len(results) == 2
    assert all(u.role in {ROLE_ADMIN, ROLE_MOD} for u in results)


def test_nested_composition_query(mongo_engine: MongoClient):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    # (admin OR mod) AND age >= 30
    results = session.scalars(
        select(LogicUser).where(
            LogicUser.tag == _TAG,
            and_(
                or_(LogicUser.role == ROLE_ADMIN, LogicUser.role == ROLE_MOD),
                LogicUser.age >= AGE_ADULT,
            ),
        )
    ).all()
    assert len(results) == 2


def test_existing_implicit_and_unchanged(mongo_engine: MongoClient):
    """Multiple simple ops in .where() still behave as implicit AND."""
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    results = session.scalars(
        select(LogicUser).where(
            LogicUser.tag == _TAG,
            LogicUser.role == ROLE_ADMIN,
            LogicUser.age == AGE_ADULT,
        )
    ).all()
    assert len(results) == 1
    assert results[0].role == ROLE_ADMIN
