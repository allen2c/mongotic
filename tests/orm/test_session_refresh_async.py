from typing import Optional

import bson
import pytest
from pymongo import AsyncMongoClient

from mongotic import Mapped, NotFound, mapped_field
from mongotic.asyncio import AsyncSession, async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_refresh_{rand_str(8)}"

    name: Mapped[str] = mapped_field()
    age: Mapped[Optional[int]] = mapped_field(default=None)


@pytest.fixture
def async_session(async_mongo_engine: AsyncMongoClient) -> AsyncSession:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_refresh_reloads_fields_from_db(
    async_session: AsyncSession, async_mongo_engine: AsyncMongoClient
) -> None:
    s = async_session
    token = rand_str(6)
    user = _U(name=f"alice_{token}", age=25)
    s.add(user)
    await s.commit()

    # Simulate external update directly via pymongo async
    await async_mongo_engine["test"][_U.__tablename__].update_one(
        {"_id": bson.ObjectId(user._id)},
        {"$set": {"age": 99}},
    )

    assert user.age == 25  # in-memory still stale
    await s.refresh(user)
    assert user.age == 99  # now up-to-date


async def test_refresh_clears_pending_updates(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    user = _U(name=f"bob_{token}", age=30)
    s.add(user)
    await s.commit()

    user.age = 31  # stage a pending update
    assert len(s.dirty) == 1

    await s.refresh(user)
    assert s.dirty == []


async def test_refresh_raises_value_error_for_unpersisted(
    async_session: AsyncSession,
) -> None:
    s = async_session
    token = rand_str(6)
    user = _U(name=f"carol_{token}", age=35)
    # Not added/flushed → _id is None
    with pytest.raises(ValueError, match="_id is None"):
        await s.refresh(user)


async def test_refresh_raises_not_found_for_deleted_doc(
    async_session: AsyncSession, async_mongo_engine: AsyncMongoClient
) -> None:
    s = async_session
    token = rand_str(6)
    user = _U(name=f"dave_{token}", age=40)
    s.add(user)
    await s.commit()

    # Delete directly from DB
    await async_mongo_engine["test"][_U.__tablename__].delete_one(
        {"_id": bson.ObjectId(user._id)}
    )

    with pytest.raises(NotFound):
        await s.refresh(user)
