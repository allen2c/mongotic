from typing import Optional, Text

import pytest
from pydantic import Field, ValidationError

from mongotic import insert
from mongotic.asyncio import async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_insert_{rand_str(8)}"

    name: Text = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine):
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_insert_bulk_dicts(async_session):
    s = async_session
    token = rand_str(6)
    result = await s.execute(
        insert(_U).values(
            [
                {"name": f"alice_{token}", "age": 10},
                {"name": f"bob_{token}", "age": 20},
            ]
        )
    )
    assert result.rowcount == 2
    assert len(result.inserted_ids) == 2
    assert all(isinstance(i, str) for i in result.inserted_ids)


async def test_insert_single_dict(async_session):
    s = async_session
    token = rand_str(6)
    result = await s.execute(insert(_U).values({"name": f"solo_{token}", "age": 10}))
    assert result.rowcount == 1
    assert len(result.inserted_ids) == 1


async def test_insert_empty_is_noop(async_session):
    s = async_session
    result = await s.execute(insert(_U).values([]))
    assert result.rowcount == 0
    assert result.inserted_ids == []


async def test_insert_from_model_instances(async_session):
    s = async_session
    token = rand_str(6)
    result = await s.execute(
        insert(_U).values([_U(name=f"x_{token}"), _U(name=f"y_{token}")])
    )
    assert result.rowcount == 2


async def test_insert_validates_in_values_call():
    with pytest.raises(ValidationError):
        insert(_U).values([{"name": 123, "age": "not-an-int"}])


async def test_insert_does_not_appear_in_session_new(async_session):
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"wt_{token}"}]))
    assert s.new == []  # write-through, no staging
