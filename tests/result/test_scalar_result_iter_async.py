from typing import Optional

import pytest
from pymongo import AsyncMongoClient

from mongotic import Mapped, insert, mapped_field, select
from mongotic.asyncio import AsyncSession, async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str

_TAG = rand_str(10)


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_iter_{rand_str(8)}"

    name: Mapped[str] = mapped_field()
    tag: Mapped[Optional[str]] = mapped_field(default=None)
    age: Mapped[Optional[int]] = mapped_field(default=None)


@pytest.fixture
def async_session(async_mongo_engine: AsyncMongoClient) -> AsyncSession:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


@pytest.fixture(autouse=True)
async def seed(async_mongo_engine):
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    s = SessionLocal()
    await s.execute(
        insert(_U).values(
            [
                {"name": "Alice", "tag": _TAG, "age": 25},
                {"name": "Bob", "tag": _TAG, "age": 30},
                {"name": "Carol", "tag": _TAG, "age": 35},
            ]
        )
    )
    yield
    await async_mongo_engine["test"][_U.__tablename__].delete_many({"tag": _TAG})


async def test_async_for_loop(async_session: AsyncSession) -> None:
    s = async_session
    stmt = select(_U).where(_U.tag == _TAG)
    names = []
    async for user in s.scalars(stmt):
        names.append(user.name)
    assert set(names) == {"Alice", "Bob", "Carol"}


async def test_all_returns_list(async_session: AsyncSession) -> None:
    s = async_session
    stmt = select(_U).where(_U.tag == _TAG)
    users = await s.scalars(stmt).all()
    assert len(users) == 3
    assert all(isinstance(u, _U) for u in users)


async def test_first_returns_one(async_session: AsyncSession) -> None:
    s = async_session
    stmt = select(_U).where(_U.tag == _TAG)
    first = await s.scalars(stmt).first()
    assert first is not None
    assert isinstance(first, _U)


async def test_one_or_none_returns_none_on_empty(async_session: AsyncSession) -> None:
    s = async_session
    result = await s.scalars(
        select(_U).where(_U.name == "ghost_zzz_not_exist")
    ).one_or_none()
    assert result is None


async def test_count(async_session: AsyncSession) -> None:
    s = async_session
    n = await s.scalars(select(_U).where(_U.tag == _TAG)).count()
    assert n == 3


async def test_exists_true(async_session: AsyncSession) -> None:
    s = async_session
    assert await s.scalars(select(_U).where(_U.tag == _TAG)).exists() is True


async def test_exists_false(async_session: AsyncSession) -> None:
    s = async_session
    assert (
        await s.scalars(select(_U).where(_U.name == "ghost_zzz_not_exist")).exists()
        is False
    )


async def test_iter_yields_hydrated_instances(async_session: AsyncSession) -> None:
    s = async_session
    async for user in s.scalars(select(_U).where(_U.tag == _TAG)):
        assert isinstance(user, _U)
        assert user._id is not None
        assert user._session is s
