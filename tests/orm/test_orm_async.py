import os
from typing import Optional

import pytest
from pydantic import Field
from pymongo import AsyncMongoClient

from mongotic import delete, insert, select, update
from mongotic.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from mongotic.model import MongoBaseModel
from mongotic.result import Result
from tests.helpers import rand_str


def test_async_engine_imports() -> None:
    from mongotic.asyncio import async_sessionmaker

    assert callable(create_async_engine)
    assert callable(async_sessionmaker)


async def test_create_async_engine_returns_async_client(
    async_mongo_engine: AsyncMongoClient,
) -> None:
    # async_mongo_engine fixture from conftest already exposes an AsyncMongoClient.
    # Here we additionally verify our create_async_engine factory:

    from mongotic.asyncio import create_async_engine

    engine = create_async_engine(os.environ["MONGODB_URI"])
    try:
        assert isinstance(engine, AsyncMongoClient)
        info = await engine.server_info()
        assert "version" in info
    finally:
        await engine.aclose()


# ── model used only in async tests ───────────────────────────────────────────


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"async_orm_{rand_str(8)}"

    name: str = Field(...)
    age: Optional[int] = Field(None)


@pytest.fixture
def async_session(async_mongo_engine: AsyncMongoClient) -> AsyncSession:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    return SessionLocal()


# ── CRUD tests ────────────────────────────────────────────────────────────────


async def test_async_add_commit_get(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    u = _U(name=f"alice_{token}", age=10)
    s.add(u)
    await s.commit()
    assert u._id is not None
    fetched = await s.get(_U, u._id)
    assert fetched.name == f"alice_{token}"


async def test_async_rollback_discards_staging(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    s.add(_U(name=f"ghost_{token}"))
    s.rollback()
    result = s.scalars(select(_U).where(_U.name == f"ghost_{token}"))
    assert await result.count() == 0


async def test_async_context_manager_commits_and_closes(
    async_mongo_engine: AsyncMongoClient,
) -> None:
    SessionLocal = async_sessionmaker(bind=async_mongo_engine)
    token = rand_str(6)
    async with SessionLocal() as s:
        s.add(_U(name=f"ctx_{token}"))
        await s.commit()
    # After context exit, staging cleared; verify via a fresh session
    async with SessionLocal() as s2:
        n = await s2.scalars(select(_U).where(_U.name == f"ctx_{token}")).count()
        assert n == 1


async def test_async_execute_update_returns_result(async_session: AsyncSession) -> None:
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
    r = await s.execute(
        update(_U).where(_U.name.in_([f"a_{token}", f"b_{token}"])).values(age=99)
    )
    assert isinstance(r, Result)
    assert r.rowcount == 2


async def test_async_execute_delete_returns_result(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"d_{token}"}, {"name": f"e_{token}"}]))
    r = await s.execute(delete(_U).where(_U.name.in_([f"d_{token}", f"e_{token}"])))

    assert r.rowcount == 2


async def test_async_execute_insert_returns_result(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    r = await s.execute(
        insert(_U).values([{"name": f"i_{token}"}, {"name": f"j_{token}"}])
    )
    assert r.rowcount == 2
    assert len(r.inserted_ids) == 2


async def test_async_scalars_first_one_or_none(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"u_{token}"}]))
    result = s.scalars(select(_U).where(_U.name == f"u_{token}"))
    first = await result.first()
    assert first is not None and first.name == f"u_{token}"
    only = await s.scalars(select(_U).where(_U.name == f"u_{token}")).one_or_none()
    assert only is not None
    nothing = await s.scalars(select(_U).where(_U.name == "nope_xyz")).one_or_none()
    assert nothing is None


@pytest.mark.cosmos_unsupported
async def test_async_for_iteration(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    names = [f"it_{token}_{i}" for i in range(3)]
    await s.execute(insert(_U).values([{"name": n} for n in names]))
    collected = []
    async for u in s.scalars(select(_U).where(_U.name.in_(names)).order_by(_U.name)):
        collected.append(u.name)
    assert sorted(collected) == sorted(names)


async def test_async_scalar_shortcut(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"sc_{token}", "age": 7}]))
    age = await s.scalar(select(_U.age).where(_U.name == f"sc_{token}"))
    assert age == 7


async def test_async_refresh(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"r_{token}", "age": 1}]))
    u = await s.scalars(select(_U).where(_U.name == f"r_{token}")).one()
    await s.execute(update(_U).where(_U.name == f"r_{token}").values(age=99))
    await s.refresh(u)
    assert u.age == 99


async def test_async_merge_upserts(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    u = _U(name=f"m_{token}", age=1)
    s.add(u)
    await s.commit()
    u.age = 2
    s.merge(u)
    await s.commit()
    reloaded = await s.scalars(select(_U).where(_U.name == f"m_{token}")).one()
    assert reloaded.age == 2


async def test_async_state_properties(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    a = _U(name=f"st_{token}")
    s.add(a)
    assert s.new == [a]
    await s.commit()
    a.name = f"st_{token}_v2"
    assert s.dirty == [a]
    s.delete(a)
    assert s.deleted == [a]


async def test_async_expunge_and_expire(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(insert(_U).values([{"name": f"ex_{token}", "age": 1}]))
    u = await s.scalars(select(_U).where(_U.name == f"ex_{token}")).one()
    u.age = 99
    assert s.dirty == [u]
    s.expunge(u)
    assert s.dirty == []
    assert u._session is None

    # re-add and expire
    s.add(u)
    s.expire(u)
    assert getattr(u, "_expired", False) is True


async def test_async_async_select_result(async_session: AsyncSession) -> None:
    s = async_session
    token = rand_str(6)
    await s.execute(
        insert(_U).values(
            [
                {"name": f"p_{token}", "age": 10},
                {"name": f"q_{token}", "age": 20},
            ]
        )
    )
    from mongotic.asyncio import AsyncSelectResult

    r = await s.execute(
        select(_U.name, _U.age).where(_U.name.in_([f"p_{token}", f"q_{token}"]))
    )
    assert isinstance(r, AsyncSelectResult)
    rows = await r.all()
    assert sorted((row.name, row.age) for row in rows) == [
        (f"p_{token}", 10),
        (f"q_{token}", 20),
    ]
