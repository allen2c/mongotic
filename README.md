# mongotic

[![PyPI](https://img.shields.io/pypi/v/mongotic.svg)](https://pypi.org/project/mongotic/)
[![Python](https://img.shields.io/pypi/pyversions/mongotic.svg)](https://pypi.org/project/mongotic/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://allen2c.github.io/mongotic/)

The concept of MongoDB, SQLAlchemy, and Pydantic combined together in one simple
and effective solution. It enables you to use SQLAlchemy v2 query syntax with
MongoDB, and lets you define data models with Pydantic.

**Documentation:** [https://allen2c.github.io/mongotic/](https://allen2c.github.io/mongotic/)

---

## v0.6.0 — Breaking change ⚠️

`mongotic` v0.6.0 introduces a new field declaration style with full IDE and
pyright support for query operators (`.in_`, `.like`, `.between`, `.is_`,
`.contains`, etc.).

```python
# v0.5 and earlier — still works at runtime, emits DeprecationWarning
name: str = Field(...)

# v0.6 and later — recommended; static-type-checks every operator
name: Mapped[str] = mapped_field()
```

- Legacy `Field()` declarations continue to work in v0.6 with a
  `DeprecationWarning` at class creation.
- The compatibility shim will be **removed in v0.7.0**.
- See the
  [migration guide](https://allen2c.github.io/mongotic/migration-v0.5-to-v0.6/)
  for the full substitution table.

---

## Overview

`mongotic` is designed to make working with MongoDB feel familiar by reusing
patterns from the SQLAlchemy and Pydantic ecosystems. It gives you a consistent
and expressive way to interact with MongoDB collections, and uses Pydantic for
validation and schema definition.

## Features

- **SQLAlchemy v2 API** — `select()`, `session.scalars()`, `ScalarResult`;
  familiar patterns without a SQL database.
- **Typed query expressions** — `Mapped[T]` descriptor makes `User.name == "x"`,
  `User.age.between(18, 65)`, `User.name.in_([...])`, and friends fully
  IDE-aware.
- **Rich query operators** — logical combinators (`or_`, `and_`, `not_`), null
  checks, string matching, range, and distinct.
- **Session management** — `refresh()`, `merge()`, `expunge()`, `expire()`,
  state inspection (`.new`, `.dirty`, `.deleted`).
- **Declarative indexes** — define `__indexes__` on the model and apply with
  `create_indexes()`; per-field `index=` / `unique=` / `sparse=` shorthand.
- **Bulk operations** — `insert()`, `update()`, and `delete()` statement
  builders via `session.execute()`, returning a `Result` with `.rowcount` and
  `.inserted_ids`.
- **Column projection** — `select(User.name, User.email)` returns lightweight
  `Row` results; single-column projection unwraps to plain values via
  `session.scalars()`.
- **Full async API** — `mongotic.asyncio` mirrors the sync session on top of
  `pymongo.AsyncMongoClient`.
- **Pydantic validation** — schema definitions, JSON schema generation, and
  every Pydantic field constraint (`min_length`, `ge`/`le`, `pattern`, etc.)
  flow through `mapped_field()`.
- **Type checking** — IDE autocomplete and pyright `basic` mode with zero
  warnings on idiomatic mongotic code.
- **Works on standalone MongoDB** — no replica set required and no
  multi-document transaction dependency.

## Installation

```bash
pip install mongotic
```

## Usage

```python
from typing import Optional

from mongotic import (
    Mapped,
    MongoBaseModel,
    MultipleResultsFound,
    NotFound,
    create_engine,
    delete,
    mapped_field,
    select,
    update,
)
from mongotic.orm import sessionmaker


class User(MongoBaseModel):
    __databasename__ = "test_database"
    __tablename__ = "user"

    name:    Mapped[str]           = mapped_field(max_length=50)
    email:   Mapped[str]           = mapped_field()
    company: Mapped[Optional[str]] = mapped_field(default=None, max_length=50)
    age:     Mapped[Optional[int]] = mapped_field(default=None, ge=0, le=200)


engine = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)

# ── Add ──────────────────────────────────────────────────────────────────────
session = Session()
session.add(User(name="Allen Chou", email="allen@example.com", company="Acme", age=30))
session.add_all([
    User(name="Bob",   email="bob@example.com",   company="Acme", age=25),
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

# Rich operators (all fully IDE-typed)
guests = session.scalars(select(User).where(User.company.in_(["Acme", "Acme Corp"]))).all()
matches = session.scalars(select(User).where(User.email.like("%@example.com"))).all()
ranged = session.scalars(select(User).where(User.age.between(18, 65))).all()

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
# Bulk update: returns Result with .rowcount
modified = session.execute(
    update(User).where(User.company == "Acme").values(company="Acme Corp")
)
# Bulk delete: returns Result with .rowcount
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

## Async usage

`mongotic.asyncio` mirrors the sync API on `pymongo.AsyncMongoClient`. See [the
async documentation](https://allen2c.github.io/mongotic/async/) for the full
reference.

```python
import asyncio
from mongotic import insert, select, update, delete
from mongotic.asyncio import create_async_engine, async_sessionmaker

async_engine = create_async_engine("mongodb://localhost:27017")
AsyncSession = async_sessionmaker(bind=async_engine)

async def main():
    async with AsyncSession() as session:
        # Bulk insert
        r = await session.execute(
            insert(User).values([
                {"name": "Alice", "email": "alice@example.com", "age": 30},
            ])
        )
        print(r.inserted_ids)   # ["<ObjectId>"]

        # Query
        adults = await session.scalars(select(User).where(User.age >= 18)).all()

        # Column projection — returns Row objects
        names = await session.scalars(select(User.name)).all()

        # Scalar shortcut
        age = await session.scalar(select(User.age).where(User.name == "Alice"))

        # Bulk update / delete
        await session.execute(update(User).where(User.company == "Acme").values(company="Acme Corp"))
        await session.execute(delete(User).where(User.age < 18))

asyncio.run(main())
```

## Contributing

Pull requests and issues are welcome. Please run `make fmt && make test` before
opening a PR.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file
for details.

## Support

If you encounter any problems or have suggestions, please open an issue or feel
free to reach out directly.
