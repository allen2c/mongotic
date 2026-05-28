from typing import Optional

import pytest
from pydantic import Field
from pymongo import AsyncMongoClient

from mongotic import delete, insert, update
from mongotic.asyncio import AsyncSession, async_sessionmaker
from mongotic.model import MongoBaseModel
from mongotic.result import Result
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_exec_result_{rand_str(8)}"

    name: str = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine: AsyncMongoClient) -> AsyncSession:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_execute_update_returns_result_with_rowcount(
    async_session: AsyncSession,
) -> None:
    s = async_session
    await s.execute(
        insert(_U).values(
            [
                {"name": "a", "age": 10},
                {"name": "b", "age": 20},
            ]
        )
    )

    result = await s.execute(update(_U).where(_U.age >= 10).values(age=99))
    assert isinstance(result, Result)
    assert result.rowcount == 2
    assert result.inserted_ids == []


async def test_execute_delete_returns_result(async_session: AsyncSession) -> None:
    s = async_session
    unique = rand_str(12)
    await s.execute(
        insert(_U).values(
            [
                {"name": f"del_{unique}_x"},
                {"name": f"del_{unique}_y"},
            ]
        )
    )

    result = await s.execute(delete(_U).where(_U.name == f"del_{unique}_x"))
    assert result.rowcount == 1
    assert result.inserted_ids == []


async def test_execute_update_zero_match(async_session: AsyncSession) -> None:
    s = async_session
    result = await s.execute(
        update(_U).where(_U.name == "ghost_xyz_not_exist").values(age=1)
    )
    assert result.rowcount == 0
