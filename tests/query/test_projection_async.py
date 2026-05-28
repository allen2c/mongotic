"""Async smoke tests for column projection via AsyncSession."""

from typing import Optional

import pytest
from pydantic import Field
from pymongo import AsyncMongoClient

from mongotic import insert, select
from mongotic.asyncio import AsyncSelectResult, AsyncSession, async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_proj_{rand_str(8)}"

    name: str = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine: AsyncMongoClient) -> AsyncSession:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_execute_select_returns_async_select_result(
    async_session: AsyncSession,
) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(
        insert(_U).values(
            [
                {"name": f"a_{token}", "age": 10},
                {"name": f"b_{token}", "age": 20},
            ]
        )
    )
    result = await s.execute(
        select(_U.name, _U.age).where(_U.name.in_([f"a_{token}", f"b_{token}"]))
    )
    assert isinstance(result, AsyncSelectResult)
    rows = await result.all()
    assert sorted((r.name, r.age) for r in rows) == [
        (f"a_{token}", 10),
        (f"b_{token}", 20),
    ]


async def test_scalars_unwraps_single_column(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(
        insert(_U).values(
            [
                {"name": f"x_{token}"},
                {"name": f"y_{token}"},
            ]
        )
    )
    names = await s.scalars(
        select(_U.name).where(_U.name.in_([f"x_{token}", f"y_{token}"]))
    ).all()
    assert sorted(names) == sorted([f"x_{token}", f"y_{token}"])


async def test_scalar_shortcut(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"sc_{token}", "age": 7}]))
    age = await s.scalar(select(_U.age).where(_U.name == f"sc_{token}"))
    assert age == 7


async def test_scalar_returns_none_when_empty(async_session: AsyncSession) -> None:
    s = async_session
    result = await s.scalar(
        select(_U.name).where(_U.name == "ghost_does_not_exist_xyz")
    )
    assert result is None


async def test_scalars_rejects_multi_column(async_session: AsyncSession) -> None:
    s = async_session
    with pytest.raises(TypeError):
        s.scalars(select(_U.name, _U.age))
