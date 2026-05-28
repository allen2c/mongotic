from typing import Optional

from pydantic import Field
from pymongo import MongoClient

from mongotic import delete, update
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from mongotic.result import Result
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"exec_result_{rand_str(8)}"

    name: str = Field(...)
    age: Optional[int] = Field(None)


def _fresh_session(mongo_engine: "MongoClient"):
    # Each test gets a clean collection because __tablename__ has a per-import suffix.
    return sessionmaker(bind=mongo_engine)()


def test_execute_update_returns_result_with_rowcount(mongo_engine: MongoClient) -> None:
    s = _fresh_session(mongo_engine)
    s.add(_U(name="a", age=10))
    s.add(_U(name="b", age=20))
    s.commit()

    result = s.execute(update(_U).where(_U.age >= 10).values(age=99))
    assert isinstance(result, Result)
    assert result.rowcount == 2
    assert result.inserted_ids == []


def test_execute_delete_returns_result(mongo_engine: MongoClient) -> None:
    s = _fresh_session(mongo_engine)
    unique = rand_str(12)
    s.add(_U(name=f"del_{unique}_x"))
    s.add(_U(name=f"del_{unique}_y"))
    s.commit()

    result = s.execute(delete(_U).where(_U.name == f"del_{unique}_x"))
    assert result.rowcount == 1
    assert result.inserted_ids == []


def test_execute_update_zero_match(mongo_engine: MongoClient) -> None:
    s = _fresh_session(mongo_engine)
    result = s.execute(update(_U).where(_U.name == "ghost").values(age=1))
    assert result.rowcount == 0
