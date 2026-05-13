# mongotic

**MongoDB + SQLAlchemy v2 + Pydantic** — use familiar SA v2 query syntax with MongoDB, define models with Pydantic.

```python
from mongotic import create_engine, select
from mongotic.orm import sessionmaker

engine  = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)

with Session() as session:
    users = session.scalars(select(User).where(User.age > 18)).all()
```

## Why mongotic?

- **Familiar API** — `select()`, `session.scalars()`, `ScalarResult` mirror SQLAlchemy v2.
- **Pydantic models** — schema validation and IDE autocomplete out of the box.
- **No replica set required** — works on standalone MongoDB instances.
- **Bulk operations** — `insert()`, `update()`, and `delete()` via `session.execute()`, returning a `Result` with `.rowcount` and `.inserted_ids`.
- **Column projection** — `select(User.name, User.email)` returns lightweight `Row` results; single-column `select(User.name)` unwraps to plain values via `session.scalars()`.
- **Full async API** — `mongotic.asyncio` mirrors the sync session on top of `pymongo.AsyncMongoClient`.

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
| [Migration Guide (v0.4 → v0.5)](migration-v0.4-to-v0.5.md) | Breaking changes and new features in v0.5.0 |
| [Migration Guide (v0.2 → v0.3)](migration-v0.2-to-v0.3.md) | Breaking changes from v0.2.0 |
| [Design](design.md) | Architecture rationale |
