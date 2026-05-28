from typing import Optional

from pydantic import Field
from pymongo import MongoClient

from mongotic import insert, select, update
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"lifecycle_{rand_str(8)}"

    name: str = Field(...)
    age: Optional[int] = Field(None)


def _s(mongo_engine):
    return sessionmaker(bind=mongo_engine)()


def test_expunge_removes_pending_updates(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    token = rand_str(6)
    s.execute(insert(_U).values([{"name": f"exp_{token}", "age": 10}]))
    u = s.scalars(select(_U).where(_U.name == f"exp_{token}")).one()
    u.age = 99
    assert s.dirty == [u]
    s.expunge(u)
    assert s.dirty == []
    assert u._session is None


def test_expunge_is_idempotent(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    token = rand_str(6)
    s.execute(insert(_U).values([{"name": f"idemp_{token}"}]))
    u = s.scalars(select(_U).where(_U.name == f"idemp_{token}")).one()
    s.expunge(u)
    s.expunge(u)  # must not raise


def test_expunge_then_readd(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    token = rand_str(6)
    s.execute(insert(_U).values([{"name": f"re_{token}"}]))
    u = s.scalars(select(_U).where(_U.name == f"re_{token}")).one()
    s.expunge(u)
    s.add(u)
    assert s.new == [u]


def test_expire_clears_pending_updates(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    token = rand_str(6)
    s.execute(insert(_U).values([{"name": f"exp_{token}", "age": 10}]))
    u = s.scalars(select(_U).where(_U.name == f"exp_{token}")).one()
    u.age = 99
    s.expire(u)
    assert s.dirty == []
    # Cached value still readable; no lazy reload
    assert u.age == 99
    assert getattr(u, "_expired", False) is True


def test_expire_does_not_reload_until_refresh(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    token = rand_str(6)
    s.execute(insert(_U).values([{"name": f"reload_{token}", "age": 10}]))
    u = s.scalars(select(_U).where(_U.name == f"reload_{token}")).one()
    # mutate the DB out-of-band
    s.execute(update(_U).where(_U.name == f"reload_{token}").values(age=42))
    s.expire(u)
    assert u.age == 10  # cached, no reload
    s.refresh(u)
    assert u.age == 42


def test_yield_per_is_chainable_and_noop(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    token = rand_str(6)
    names = [f"yp_{token}_{i}" for i in range(3)]
    s.execute(insert(_U).values([{"name": n} for n in names]))
    stmt = select(_U).where(_U.name.in_(names)).yield_per(2)
    rows = s.scalars(stmt).all()
    assert sorted(u.name for u in rows) == sorted(names)
