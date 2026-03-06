# mongotic

The concept of MongoDB, SQLAlchemy, and Pydantic combined together in one simple and effective solution. It enables you to use SQLAlchemy v2 query syntax with MongoDB, and allows you to define your data models using Pydantic.

**Documentation:** [https://allen2c.github.io/mongotic/](https://allen2c.github.io/mongotic/)

> **Project management:** Issues and epics are tracked with [PLANK](https://github.com/allen2c/PLANK) under `.plank/`.

## Overview

The `mongotic` library is designed to make working with MongoDB as seamless as possible by using familiar tools and patterns from the SQLAlchemy and Pydantic ecosystems. It provides a consistent and expressive way to interact with MongoDB collections, and utilises Pydantic for validation and data definition.

## Features

- **SQLAlchemy v2 API**: `select()`, `session.scalars()`, `ScalarResult` — familiar patterns without a SQL database.
- **Rich query operators**: logical combinators (`or_`, `and_`, `not_`), null checks, string matching, range, and distinct.
- **Session management**: `refresh()`, `merge()`, state inspection (`.new`, `.dirty`, `.deleted`).
- **Declarative indexes**: define `__indexes__` on the model, apply with `create_indexes()`.
- **Bulk Operations**: `update()` and `delete()` statement builders via `session.execute()`.
- **Data Validation**: Utilise Pydantic's powerful schema definition for data validation and serialisation.
- **Type Checking**: Benefit from type checking and autocomplete in IDEs due to static type definitions.
- **Works on standalone MongoDB**: No replica set required — no multi-document transaction dependency.

## Installation

```bash
pip install mongotic
```

## Usage

> **v0.3.0 breaking change**: `session.query()` has been removed. Use `select()` + `session.scalars()` instead.

```python
from typing import Optional, Text

from pydantic import Field

from mongotic import MultipleResultsFound, NotFound, create_engine, delete, select, update
from mongotic.model import MongoBaseModel
from mongotic.orm import sessionmaker


class User(MongoBaseModel):
    __databasename__ = "test_database"
    __tablename__ = "user"

    name: Text = Field(..., max_length=50)
    email: Text = Field(...)
    company: Optional[Text] = Field(None, max_length=50)
    age: Optional[int] = Field(None, ge=0, le=200)


engine = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)

# ── Add ──────────────────────────────────────────────────────────────────────
session = Session()
session.add(User(name="Allen Chou", email="allen@example.com", company="Acme", age=30))
session.add_all([
    User(name="Bob", email="bob@example.com", company="Acme", age=25),
    User(name="Carol", email="carol@example.com", company="Acme", age=28),
])
session.commit()

# ── Query ────────────────────────────────────────────────────────────────────
session = Session()

# Fetch all / first
users = session.scalars(select(User)).all()
users = session.scalars(select(User).where(User.age > 18)).all()
users = session.scalars(
    select(User)
    .where(User.company == "Acme")
    .order_by(-User.age)      # descending; use User.age for ascending
    .limit(10)
    .offset(0)
).all()

user = session.scalars(select(User).where(User.email == "allen@example.com")).first()
user = session.get(User, "<object_id_string>")   # PK lookup; returns None if not found

# Strict single-result fetch
try:
    user = session.scalars(select(User).where(User.email == "allen@example.com")).one()
    # raises NotFound if 0 results; raises MultipleResultsFound if 2+ results
except NotFound:
    ...
except MultipleResultsFound:
    ...

user = session.scalars(
    select(User).where(User.email == "allen@example.com")
).one_or_none()
# returns None if 0 results; raises MultipleResultsFound if 2+ results

# Count and existence check
count = session.scalars(select(User).where(User.company == "Acme")).count()
exists = session.scalars(select(User).where(User.company == "Acme")).exists()

# ── Update ───────────────────────────────────────────────────────────────────
session = Session()
user = session.scalars(select(User).where(User.email == "allen@example.com")).first()
user.email = "new.allen@example.com"   # tracked automatically
session.commit()

# ── Delete ───────────────────────────────────────────────────────────────────
session = Session()
user = session.scalars(select(User).where(User.email == "new.allen@example.com")).first()
session.delete(user)
session.commit()

# ── Bulk Operations ──────────────────────────────────────────────────────────
session = Session()
# Bulk update: returns number of modified documents
modified = session.execute(
    update(User).where(User.company == "Acme").values(company="Acme Corp")
)
# Bulk delete: returns number of deleted documents
deleted = session.execute(
    delete(User).where(User.age < 18)
)

# ── Context manager + flush ──────────────────────────────────────────────────
with Session() as session:
    new_user = User(name="Dave", email="dave@example.com", age=35)
    session.add(new_user)
    session.flush()          # writes immediately; new_user._id is now available
    print(new_user._id)
    session.commit()         # alias for flush()
```

## Contributing

TODO

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Support

If you encounter any problems or have suggestions, please open an issue, or feel free to reach out directly.
