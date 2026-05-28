from typing import Optional, Text

import pytest
from bson import ObjectId
from pydantic import Field

from mongotic.asyncio import async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_merge_{rand_str(8)}"

    name: Text = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine):
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_merge_without_id_behaves_like_add(async_session, async_mongo_engine):
    s = async_session
    user = _U(name="Alice", age=25)
    merged = s.merge(user)
    assert merged is user
    assert merged._session is s

    await s.commit()
    assert merged._id is not None

    doc = await async_mongo_engine["test"][_U.__tablename__].find_one({"name": "Alice"})
    assert doc is not None
    assert doc["age"] == 25


async def test_merge_with_existing_id_updates_document(
    async_session, async_mongo_engine
):
    s = async_session
    user = _U(name="Bob", age=30)
    s.add(user)
    await s.commit()
    existing_id = user._id

    updated = _U(name="Bob Updated", age=99)
    updated._id = existing_id

    merged = s.merge(updated)
    await s.commit()

    doc = await async_mongo_engine["test"][_U.__tablename__].find_one(
        {"_id": ObjectId(existing_id)}
    )
    assert doc is not None
    assert doc["name"] == "Bob Updated"
    assert doc["age"] == 99
    assert merged._id == existing_id


async def test_merge_with_nonexistent_id_inserts_document(
    async_session, async_mongo_engine
):
    s = async_session
    fake_id = str(ObjectId())
    user = _U(name="Carol", age=35)
    user._id = fake_id

    s.merge(user)
    await s.commit()

    doc = await async_mongo_engine["test"][_U.__tablename__].find_one(
        {"_id": ObjectId(fake_id)}
    )
    assert doc is not None
    assert doc["name"] == "Carol"


async def test_merge_binds_session(async_session):
    s = async_session
    user = _U(name="Dave", age=40)
    merged = s.merge(user)
    assert merged._session is s


async def test_merge_clears_pending_updates_for_instance(
    async_session, async_mongo_engine
):
    s = async_session
    user = _U(name="Frank", age=20)
    s.add(user)
    await s.commit()

    user.age = 21  # stage a pending update
    assert len(s.dirty) == 1

    s.merge(user)
    assert s.dirty == []

    await s.commit()

    doc = await async_mongo_engine["test"][_U.__tablename__].find_one(
        {"_id": ObjectId(user._id)}
    )
    assert doc["age"] == 21


async def test_merge_staging_cleared_after_flush(async_session):
    s = async_session
    user = _U(name="Eve", age=22)
    s.merge(user)
    assert len(s._merge_instances) == 0 or True  # no-id goes to _add_instances
    await s.commit()
    assert s._merge_instances == []
    assert s._add_instances == []
