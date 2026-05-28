"""Async smoke tests for or_(), and_(), not_() logical combinators via AsyncSession."""

from typing import Text

import pytest
from pydantic import Field

from mongotic import and_, insert, not_, or_, select
from mongotic.asyncio import async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str

_TAG = rand_str(10)

ROLE_ADMIN = "admin"
ROLE_MOD = "moderator"
ROLE_GUEST = "guest"
AGE_ADULT = 30
AGE_MINOR = 15


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_logic_{rand_str(8)}"

    tag: Text = Field(...)
    role: Text = Field(...)
    age: int = Field(...)


@pytest.fixture
def async_session(async_mongo_engine):
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


@pytest.fixture(autouse=True)
async def seed_and_cleanup(async_mongo_engine):
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    s = SessionLocal()
    await s.execute(
        insert(_U).values(
            [
                {"tag": _TAG, "role": ROLE_ADMIN, "age": AGE_ADULT},
                {"tag": _TAG, "role": ROLE_MOD, "age": AGE_ADULT},
                {"tag": _TAG, "role": ROLE_GUEST, "age": AGE_MINOR},
            ]
        )
    )
    yield
    await async_mongo_engine["test"][_U.__tablename__].delete_many({"tag": _TAG})


async def test_or_query(async_session):
    s = async_session
    results = await s.scalars(
        select(_U).where(
            _U.tag == _TAG,
            or_(_U.role == ROLE_ADMIN, _U.role == ROLE_MOD),
        )
    ).all()
    assert len(results) == 2
    roles = {u.role for u in results}
    assert roles == {ROLE_ADMIN, ROLE_MOD}


async def test_and_query(async_session):
    s = async_session
    results = await s.scalars(
        select(_U).where(
            _U.tag == _TAG,
            and_(_U.age >= AGE_ADULT, _U.role == ROLE_ADMIN),
        )
    ).all()
    assert len(results) == 1
    assert results[0].role == ROLE_ADMIN


async def test_not_single_query(async_session):
    s = async_session
    results = await s.scalars(
        select(_U).where(
            _U.tag == _TAG,
            not_(_U.role == ROLE_GUEST),
        )
    ).all()
    assert len(results) == 2
    assert all(u.role != ROLE_GUEST for u in results)


async def test_not_or_nor_query(async_session):
    s = async_session
    results = await s.scalars(
        select(_U).where(
            _U.tag == _TAG,
            not_(or_(_U.role == ROLE_GUEST, _U.role == "anonymous")),
        )
    ).all()
    assert len(results) == 2
    assert all(u.role in {ROLE_ADMIN, ROLE_MOD} for u in results)


async def test_nested_composition_query(async_session):
    s = async_session
    results = await s.scalars(
        select(_U).where(
            _U.tag == _TAG,
            and_(
                or_(_U.role == ROLE_ADMIN, _U.role == ROLE_MOD),
                _U.age >= AGE_ADULT,
            ),
        )
    ).all()
    assert len(results) == 2
