from typing import Optional

import pytest
from pymongo import MongoClient

from mongotic import Mapped, insert, mapped_field, select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from mongotic.result import Row, SelectResult
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"projection_{rand_str(8)}"

    name: Mapped[str] = mapped_field()
    age: Mapped[Optional[int]] = mapped_field(default=None)


def _s(mongo_engine):
    return sessionmaker(bind=mongo_engine)()


def _seed(mongo_engine, items):
    s = _s(mongo_engine)
    s.execute(insert(_U).values(items))
    return s


def test_row_attr_access() -> None:
    row = Row(("alice", "a@x"), ("name", "email"))
    assert row.name == "alice"
    assert row.email == "a@x"


def test_row_index_access() -> None:
    row = Row(("alice", "a@x"), ("name", "email"))
    assert row[0] == "alice"
    assert row[1] == "a@x"


def test_row_key_access() -> None:
    row = Row(("alice", "a@x"), ("name", "email"))
    assert row["name"] == "alice"
    assert row["email"] == "a@x"


def test_row_asdict() -> None:
    row = Row(("alice", "a@x"), ("name", "email"))
    assert row._asdict() == {"name": "alice", "email": "a@x"}


def test_row_iter_and_len() -> None:
    row = Row(("alice", "a@x"), ("name", "email"))
    assert list(row) == ["alice", "a@x"]
    assert len(row) == 2


def test_row_repr() -> None:
    row = Row(("alice",), ("name",))
    assert "Row" in repr(row) and "alice" in repr(row)


def test_row_is_immutable() -> None:
    row = Row(("alice",), ("name",))
    with pytest.raises(AttributeError):
        row.name = "bob"


# ── projection integration tests ─────────────────────────────────────────────


def test_execute_select_returns_select_result(mongo_engine: MongoClient) -> None:
    token = rand_str(6)
    s = _seed(
        mongo_engine,
        [
            {"name": f"a_{token}", "age": 10},
            {"name": f"b_{token}", "age": 20},
        ],
    )
    result = s.execute(
        select(_U.name, _U.age).where(_U.name.in_([f"a_{token}", f"b_{token}"]))
    )
    assert isinstance(result, SelectResult)
    rows = result.all()
    assert all(isinstance(r, Row) for r in rows)
    assert sorted((r.name, r.age) for r in rows) == [
        (f"a_{token}", 10),
        (f"b_{token}", 20),
    ]


def test_projection_drops_id_by_default(mongo_engine: MongoClient) -> None:
    from mongotic.result import SelectResult

    token = rand_str(6)
    s = _seed(mongo_engine, [{"name": f"k_{token}"}])
    result = s.execute(select(_U.name).where(_U.name == f"k_{token}"))
    assert isinstance(result, SelectResult)
    row = result.first()
    assert row is not None
    with pytest.raises(AttributeError):
        _ = row._id


def test_scalars_unwraps_single_column(mongo_engine: MongoClient) -> None:
    token = rand_str(6)
    s = _seed(
        mongo_engine,
        [{"name": f"x_{token}"}, {"name": f"y_{token}"}],
    )
    names = s.scalars(
        select(_U.name).where(_U.name.in_([f"x_{token}", f"y_{token}"]))
    ).all()
    assert sorted(names) == sorted([f"x_{token}", f"y_{token}"])


def test_scalars_rejects_multi_column(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    with pytest.raises(TypeError):
        s.scalars(select(_U.name, _U.age))


def test_mixed_entities_raise() -> None:
    with pytest.raises(TypeError):
        select(_U, _U.name)  # type: ignore[call-overload]


def test_select_no_args_raises() -> None:
    with pytest.raises(TypeError):
        select()


def test_scalar_returns_single_value(mongo_engine: MongoClient) -> None:
    token = rand_str(6)
    s = _seed(mongo_engine, [{"name": f"sc_{token}", "age": 10}])
    name = s.scalar(select(_U.name).where(_U.name == f"sc_{token}"))
    assert name == f"sc_{token}"


def test_scalar_returns_none_when_empty(mongo_engine: MongoClient) -> None:
    s = _s(mongo_engine)
    assert s.scalar(select(_U.name).where(_U.name == "ghost_does_not_exist")) is None


def test_scalar_returns_first_for_full_model(mongo_engine: MongoClient) -> None:
    token = rand_str(6)
    s = _seed(mongo_engine, [{"name": f"fm_{token}"}])
    obj = s.scalar(select(_U).where(_U.name == f"fm_{token}"))
    assert obj is not None
    assert obj.name == f"fm_{token}"
