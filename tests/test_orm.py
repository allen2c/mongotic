from datetime import datetime
from typing import Optional, Text

import pytest
from pydantic import Field
from pymongo import MongoClient

from mongotic import MultipleResultsFound, NotFound, delete, select, update
from mongotic.model import MongoBaseModel
from mongotic.orm import ScalarResult, sessionmaker
from tests.helpers import rand_str, utc_now

test_company = f"test_{rand_str(10)}"


class User(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "user"

    name: Text = Field(..., max_length=50)
    email: Text = Field(...)
    company: Optional[Text] = Field(None, max_length=50)
    age: Optional[int] = Field(None, ge=0, le=200)
    created_at: Optional[datetime] = Field(..., default_factory=utc_now)
    updated_at: Optional[datetime] = Field(..., default_factory=utc_now)


def test_session_maker(mongo_engine: "MongoClient"):
    Session_1 = sessionmaker(bind=mongo_engine)
    Session_2 = sessionmaker(bind=mongo_engine)
    assert (Session_1() == Session_2()) is False


def test_add_operation(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    new_user = User(
        name="John Doe", email="johndoe@example.com", company=test_company, age=30
    )
    session.add(new_user)
    session.commit()
    assert new_user._id is not None


def test_add_all_operation(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = [
        User(name="Alice", email="alice@example.com", company=test_company, age=25),
        User(name="Bob", email="bob@example.com", company=test_company, age=28),
    ]
    session.add_all(users)
    session.commit()
    assert all(u._id is not None for u in users)


def test_scalars_all(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    stmt = select(User).where(User.company == test_company)
    result = session.scalars(stmt)
    assert isinstance(result, ScalarResult)

    users = result.all()
    assert len(users) > 0


def test_scalars_first(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    user = session.scalars(select(User).where(User.company == test_company)).first()
    assert user is not None

    missing = session.scalars(
        select(User).where(User.company == "NO_SUCH_COMPANY")
    ).first()
    assert missing is None


def test_scalars_filter(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = session.scalars(
        select(User).where(User.company == test_company, User.age > 20)
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age > 200)
    ).all()
    assert len(users) == 0


def test_scalars_count_and_exists(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    count = session.scalars(select(User).where(User.company == test_company)).count()
    assert count > 0

    exists = session.scalars(select(User).where(User.company == test_company)).exists()
    assert exists is True

    no_exists = session.scalars(
        select(User).where(User.company == "NO_SUCH_COMPANY")
    ).exists()
    assert no_exists is False


def test_scalars_order_by_and_limit(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = session.scalars(
        select(User).where(User.company == test_company).order_by(User.name).limit(2)
    ).all()
    assert len(users) <= 2


def test_get(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    existing = session.scalars(select(User).where(User.company == test_company)).first()
    assert existing is not None

    fetched = session.get(User, existing._id)
    assert fetched is not None
    assert fetched._id == existing._id

    missing = session.get(User, "000000000000000000000000")
    assert missing is None


def test_update_via_setattr(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    user = session.scalars(select(User).where(User.company == test_company)).first()
    assert user is not None

    user.email = "updated@example.com"
    session.commit()


def test_context_manager_and_flush(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)

    with Session() as session:
        new_user = User(
            name="FlushTest", email="flush@example.com", company=test_company, age=99
        )
        session.add(new_user)
        session.flush()
        assert new_user._id is not None
        session.commit()


def test_scalars_one(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    # 1 result → returns the instance
    existing = session.scalars(select(User).where(User.company == test_company)).first()
    assert existing is not None
    user = session.scalars(select(User).where(User.email == existing.email)).one()
    assert user._id == existing._id

    # 0 results → raises NotFound
    with pytest.raises(NotFound):
        session.scalars(select(User).where(User.company == "NO_SUCH_COMPANY")).one()

    # 2+ results → raises MultipleResultsFound
    with pytest.raises(MultipleResultsFound):
        session.scalars(select(User).where(User.company == test_company)).one()


def test_scalars_one_or_none(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    # 1 result → returns the instance
    existing = session.scalars(select(User).where(User.company == test_company)).first()
    assert existing is not None
    user = session.scalars(
        select(User).where(User.email == existing.email)
    ).one_or_none()
    assert user is not None
    assert user._id == existing._id

    # 0 results → returns None
    result = session.scalars(
        select(User).where(User.company == "NO_SUCH_COMPANY")
    ).one_or_none()
    assert result is None

    # 2+ results → raises MultipleResultsFound
    with pytest.raises(MultipleResultsFound):
        session.scalars(select(User).where(User.company == test_company)).one_or_none()


def test_execute_bulk_update(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    # Ensure there are users to update
    count = session.scalars(select(User).where(User.company == test_company)).count()
    assert count > 0

    stmt = update(User).where(User.company == test_company).values(age=99)
    modified = session.execute(stmt)
    assert modified > 0

    # Verify all matching documents now have age=99
    users = session.scalars(
        select(User).where(User.company == test_company, User.age == 99)
    ).all()
    assert len(users) == count


def test_execute_bulk_delete(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    bulk_company = f"bulk_delete_{rand_str(8)}"
    session.add_all(
        [
            User(name="BulkA", email="bulka@example.com", company=bulk_company, age=10),
            User(name="BulkB", email="bulkb@example.com", company=bulk_company, age=20),
        ]
    )
    session.commit()

    count_before = session.scalars(
        select(User).where(User.company == bulk_company)
    ).count()
    assert count_before == 2

    stmt = delete(User).where(User.company == bulk_company)
    deleted = session.execute(stmt)
    assert deleted == 2

    count_after = session.scalars(
        select(User).where(User.company == bulk_company)
    ).count()
    assert count_after == 0


def test_delete_operation(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = session.scalars(select(User).where(User.company == test_company)).all()
    assert len(users) > 0

    for user in users:
        session.delete(user)
    session.commit()

    remaining = session.scalars(
        select(User).where(User.company == test_company)
    ).count()
    assert remaining == 0
