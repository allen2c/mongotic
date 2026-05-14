from datetime import datetime
from typing import Optional, Text

from pydantic import Field
from pymongo import MongoClient

from mongotic import select
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker
from tests.helpers import rand_str, utc_now

test_name = f"test_{rand_str(10)}"
test_email = f"test_{rand_str(10)}@example.com"
test_company = f"test_{rand_str(10)}"
test_age = 25


class User(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "user"

    name: Text = Field(..., max_length=50)
    email: Text = Field(...)
    company: Optional[Text] = Field(None, max_length=50)
    age: Optional[int] = Field(None, ge=0, le=200)
    created_at: Optional[datetime] = Field(..., default_factory=utc_now)
    updated_at: Optional[datetime] = Field(..., default_factory=utc_now)


def test_init_documents(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    new_user = User(
        name=test_name,
        email=test_email,
        company=test_company,
        age=test_age,
    )
    session.add(new_user)
    session.commit()


def test_query_filter_operators(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = session.scalars(
        select(User).where(User.company == test_company, User.name == test_name)
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.name == "NAME NOT EXISTS")
    ).all()
    assert len(users) == 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.name != test_name)
    ).all()
    assert len(users) == 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.name != "NAME NOT EXISTS")
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age > test_age)
    ).all()
    assert len(users) == 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age > test_age - 1)
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age >= test_age)
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age < test_age)
    ).all()
    assert len(users) == 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age < test_age + 1)
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.age <= test_age)
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.name.in_([test_name]))
    ).all()
    assert len(users) > 0

    users = session.scalars(
        select(User).where(
            User.company == test_company, User.name.in_(["NAME NOT EXISTS"])
        )
    ).all()
    assert len(users) == 0

    users = session.scalars(
        select(User).where(User.company == test_company, User.name.not_in([test_name]))
    ).all()
    assert len(users) == 0

    users = session.scalars(
        select(User).where(
            User.company == test_company, User.name.not_in(["NAME NOT EXISTS"])
        )
    ).all()
    assert len(users) > 0


def test_clean_documents(mongo_engine: "MongoClient"):
    Session = sessionmaker(bind=mongo_engine)
    session = Session()

    users = session.scalars(
        select(User).where(User.company == test_company).limit(10)
    ).all()

    for user in users:
        session.delete(user)

    session.commit()
