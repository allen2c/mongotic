from typing import Optional, Text

import pytest
from pydantic import Field, ValidationError

from mongotic import insert, select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"insert_stmt_{rand_str(8)}"

    name: Text = Field(...)
    age: Optional[int] = Field(None)


def _s(mongo_engine):
    return sessionmaker(bind=mongo_engine)()


def test_insert_bulk_dicts(mongo_engine):
    s = _s(mongo_engine)
    token = rand_str(6)
    result = s.execute(
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


def test_insert_single_dict(mongo_engine):
    s = _s(mongo_engine)
    token = rand_str(6)
    result = s.execute(insert(_U).values({"name": f"solo_{token}", "age": 10}))
    assert result.rowcount == 1
    assert len(result.inserted_ids) == 1


def test_insert_empty_is_noop(mongo_engine):
    s = _s(mongo_engine)
    result = s.execute(insert(_U).values([]))
    assert result.rowcount == 0
    assert result.inserted_ids == []


def test_insert_from_model_instances(mongo_engine):
    s = _s(mongo_engine)
    token = rand_str(6)
    result = s.execute(
        insert(_U).values([_U(name=f"x_{token}"), _U(name=f"y_{token}")])
    )
    assert result.rowcount == 2


def test_insert_validates_in_values_call(mongo_engine):
    with pytest.raises(ValidationError):
        insert(_U).values([{"name": 123, "age": "not-an-int"}])


def test_insert_does_not_appear_in_session_new(mongo_engine):
    s = _s(mongo_engine)
    token = rand_str(6)
    s.execute(insert(_U).values([{"name": f"wt_{token}"}]))
    assert s.new == []  # write-through, no staging
