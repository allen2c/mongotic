from typing import Optional

import pytest
from pydantic import Field
from pymongo import AsyncMongoClient

from mongotic.asyncio import AsyncSession, async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_state_{rand_str(8)}"

    name: str = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine: AsyncMongoClient) -> AsyncSession:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_new_reflects_staged_adds(async_session: AsyncSession) -> None:
    s = async_session
    assert s.new == []
    user = _U(name="Alice", age=25)
    s.add(user)
    assert len(s.new) == 1
    assert s.new[0] is user


async def test_new_empty_after_flush(async_session: AsyncSession) -> None:
    s = async_session
    s.add(_U(name="Alice", age=25))
    await s.commit()
    assert s.new == []


async def test_dirty_reflects_field_changes(async_session: AsyncSession) -> None:
    s = async_session
    user = _U(name="Bob", age=30)
    s.add(user)
    await s.commit()

    assert s.dirty == []
    user.age = 31
    dirty = s.dirty
    assert len(dirty) == 1
    assert dirty[0] is user


async def test_dirty_deduplicates_multiple_field_changes(
    async_session: AsyncSession,
) -> None:
    s = async_session
    user = _U(name="Carol", age=35)
    s.add(user)
    await s.commit()

    user.age = 36
    user.name = "Carol Updated"
    assert len(s.dirty) == 1
    assert s.dirty[0] is user


async def test_dirty_empty_after_flush(async_session: AsyncSession) -> None:
    s = async_session
    user = _U(name="Dave", age=40)
    s.add(user)
    await s.commit()
    user.age = 41
    await s.commit()
    assert s.dirty == []


async def test_deleted_reflects_staged_deletes(async_session: AsyncSession) -> None:
    s = async_session
    user = _U(name="Eve", age=22)
    s.add(user)
    await s.commit()

    assert s.deleted == []
    s.delete(user)
    assert len(s.deleted) == 1
    assert s.deleted[0] is user


async def test_deleted_empty_after_flush(async_session: AsyncSession) -> None:
    s = async_session
    user = _U(name="Frank", age=28)
    s.add(user)
    await s.commit()
    s.delete(user)
    await s.commit()
    assert s.deleted == []


async def test_state_properties_return_shallow_copies(
    async_session: AsyncSession,
) -> None:
    s = async_session
    user = _U(name="Grace", age=33)
    s.add(user)

    new_copy = s.new
    new_copy.clear()
    assert len(s.new) == 1
