from typing import Optional

import pytest
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.operations import IndexModel

from mongotic import Mapped, mapped_field
from mongotic.asyncio import async_sessionmaker, create_async_indexes
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str

_SUFFIX = rand_str(8)


class _UserWithIndexes(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_idx_{_SUFFIX}"
    __indexes__ = [
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("created_at", DESCENDING)]),
    ]

    email: Mapped[str] = mapped_field()
    name: Mapped[Optional[str]] = mapped_field(default=None)
    created_at: Mapped[Optional[int]] = mapped_field(default=None)


class _UserNoIndexes(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_noidx_{_SUFFIX}"

    name: Mapped[str] = mapped_field()


@pytest.fixture(autouse=True)
async def cleanup(async_mongo_engine):
    yield
    await async_mongo_engine["test"][_UserWithIndexes.__tablename__].drop()
    await async_mongo_engine["test"][_UserNoIndexes.__tablename__].drop()


@pytest.mark.cosmos_unsupported
async def test_create_async_indexes_applies_to_collection(
    async_mongo_engine: AsyncMongoClient,
) -> None:
    await create_async_indexes(async_mongo_engine, _UserWithIndexes)

    index_info = await async_mongo_engine["test"][
        _UserWithIndexes.__tablename__
    ].index_information()
    index_keys = [
        tuple(v["key"]) for v in index_info.values() if v["key"] != [("_id", 1)]
    ]
    assert ("email", 1) in [k[0] for k in index_keys]
    assert ("created_at", -1) in [k[0] for k in index_keys]


@pytest.mark.cosmos_unsupported
async def test_create_async_indexes_unique_enforced(
    async_mongo_engine: AsyncMongoClient,
) -> None:
    from pymongo.errors import DuplicateKeyError

    await create_async_indexes(async_mongo_engine, _UserWithIndexes)
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)

    s1 = SessionLocal()
    s1.add(_UserWithIndexes(email="alice@example.com", name="Alice"))
    await s1.commit()

    s2 = SessionLocal()
    s2.add(_UserWithIndexes(email="alice@example.com", name="Alice Duplicate"))
    with pytest.raises(DuplicateKeyError):
        await s2.commit()


async def test_create_async_indexes_skips_model_without_indexes(
    async_mongo_engine: AsyncMongoClient,
) -> None:
    await create_async_indexes(async_mongo_engine, _UserNoIndexes)

    index_info = await async_mongo_engine["test"][
        _UserNoIndexes.__tablename__
    ].index_information()
    non_id_indexes = [k for k in index_info if k != "_id_"]
    assert non_id_indexes == []


@pytest.mark.cosmos_unsupported
async def test_create_async_indexes_accepts_multiple_models(
    async_mongo_engine: AsyncMongoClient,
) -> None:
    await create_async_indexes(async_mongo_engine, _UserWithIndexes, _UserNoIndexes)

    index_info = await async_mongo_engine["test"][
        _UserWithIndexes.__tablename__
    ].index_information()
    assert len(index_info) > 1  # _id + custom indexes


async def test_indexes_class_attribute_not_instance_field() -> None:
    user = _UserWithIndexes(email="test@example.com")
    assert "indexes" not in user.model_dump()
    assert "__indexes__" not in user.model_dump()


def test_default_indexes_is_empty_list() -> None:
    assert _UserNoIndexes.__indexes__ == []
