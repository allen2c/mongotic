"""Documents the v0.4 → v0.5 break: session.execute() now returns Result, not int."""

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import update
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = f"exec_migration_{rand_str(8)}"

    name: str = Field(...)


def test_old_v0_4_form_now_raises(mongo_engine: MongoClient) -> None:
    s = sessionmaker(bind=mongo_engine)()
    result = s.execute(update(_U).where(_U.name == "x").values(name="y"))

    # Old code treating return as int will fail:
    with pytest.raises(TypeError):
        _ = result + 1  # Result is not an int

    # New code:
    assert isinstance(result.rowcount, int)
