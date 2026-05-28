from typing import Optional, Text

import pytest
from pydantic import Field

from mongotic import insert, select, update
from mongotic.asyncio import async_sessionmaker
from mongotic.model import MongoBaseModel
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_lifecycle_{rand_str(8)}"

    name: Text = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine):
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


async def test_expunge_removes_pending_updates(async_session):
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"exp_{token}", "age": 10}]))
    u = await s.scalars(select(_U).where(_U.name == f"exp_{token}")).one()
    u.age = 99
    assert s.dirty == [u]
    s.expunge(u)
    assert s.dirty == []
    assert u._session is None


async def test_expunge_is_idempotent(async_session):
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"idemp_{token}"}]))
    u = await s.scalars(select(_U).where(_U.name == f"idemp_{token}")).one()
    s.expunge(u)
    s.expunge(u)  # must not raise


async def test_expunge_then_readd(async_session):
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"re_{token}"}]))
    u = await s.scalars(select(_U).where(_U.name == f"re_{token}")).one()
    s.expunge(u)
    s.add(u)
    assert s.new == [u]


async def test_expire_clears_pending_updates(async_session):
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"exp_{token}", "age": 10}]))
    u = await s.scalars(select(_U).where(_U.name == f"exp_{token}")).one()
    u.age = 99
    s.expire(u)
    assert s.dirty == []
    assert u.age == 99
    assert getattr(u, "_expired", False) is True


async def test_expire_does_not_reload_until_refresh(async_session):
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"reload_{token}", "age": 10}]))
    u = await s.scalars(select(_U).where(_U.name == f"reload_{token}")).one()
    await s.execute(update(_U).where(_U.name == f"reload_{token}").values(age=42))
    s.expire(u)
    assert u.age == 10  # cached, no reload
    await s.refresh(u)
    assert u.age == 42


async def test_yield_per_is_chainable_and_noop(async_session):
    s = async_session
    token = rand_str(6)
    names = [f"yp_{token}_{i}" for i in range(3)]
    await s.execute(insert(_U).values([{"name": n} for n in names]))
    stmt = select(_U).where(_U.name.in_(names)).yield_per(2)
    rows = await s.scalars(stmt).all()
    assert sorted(u.name for u in rows) == sorted(names)
