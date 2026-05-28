# mongotic

**MongoDB + SQLAlchemy v2 + Pydantic** — use familiar SA v2 query syntax with
MongoDB, define models with Pydantic, and get full IDE / pyright support for
every query operator.

```python
from mongotic import Mapped, MongoBaseModel, create_engine, mapped_field, select
from mongotic.orm import sessionmaker


class User(MongoBaseModel):
    __databasename__ = "myapp"
    __tablename__    = "users"

    name: Mapped[str] = mapped_field()
    age:  Mapped[int] = mapped_field(default=0)


engine  = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)

with Session() as session:
    users = session.scalars(select(User).where(User.age > 18)).all()
```

!!! warning "v0.6.0 introduces a new field declaration style"
    Fields are now declared with `Mapped[T] = mapped_field(...)` instead of
    `T = Field(...)`. The old style still works at runtime in v0.6 but emits a
    `DeprecationWarning` and **will be removed in v0.7.0**. See the
    [migration guide](migration-v0.5-to-v0.6.md) for the substitution recipe.

## Why mongotic?

- **Familiar API** — `select()`, `session.scalars()`, `ScalarResult` mirror
  SQLAlchemy v2.
- **Typed query expressions** — the `Mapped[T]` descriptor makes
  `User.name == "x"`, `User.age.between(18, 65)`, `User.email.is_(None)`, and
  every other operator fully IDE-aware.
- **Pydantic models** — schema validation, JSON schema generation, and field
  constraints flow through `mapped_field()`.
- **No replica set required** — works on standalone MongoDB instances.
- **Bulk operations** — `insert()`, `update()`, and `delete()` via
  `session.execute()`, returning a `Result` with `.rowcount` and
  `.inserted_ids`.
- **Column projection** — `select(User.name, User.email)` returns lightweight
  `Row` results; single-column `select(User.name)` unwraps to plain values via
  `session.scalars()`.
- **Full async API** — `mongotic.asyncio` mirrors the sync session on top of
  `pymongo.AsyncMongoClient`.

## Installation

```bash
pip install mongotic
```

## Navigation

| Page | What it covers |
|------|---------------|
| [Quickstart](quickstart.md) | End-to-end example in under 5 minutes |
| [Querying](querying.md) | `select()`, filters, logical combinators, string/range/null operators, distinct, projection, `ScalarResult` |
| [Session](session.md) | Session lifecycle, writes, refresh, merge, expunge/expire, state properties |
| [Indexes](indexes.md) | `__indexes__` declaration and `create_indexes()` |
| [Async](async.md) | Full async API via `mongotic.asyncio` |
| [Migration Guide (v0.5 → v0.6)](migration-v0.5-to-v0.6.md) | **Breaking:** `Mapped[T]` / `mapped_field()` declaration style |
| [Migration Guide (v0.4 → v0.5)](migration-v0.4-to-v0.5.md) | Breaking changes and new features in v0.5.0 |
| [Migration Guide (v0.2 → v0.3)](migration-v0.2-to-v0.3.md) | Breaking changes from v0.2.0 |
| [Design](design.md) | Architecture rationale |
