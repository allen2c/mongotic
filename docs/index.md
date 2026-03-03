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
- **Bulk operations** — `update()` and `delete()` via `session.execute()`.

## Installation

```bash
pip install mongotic
```

## Navigation

| Page | What it covers |
|------|---------------|
| [Quickstart](quickstart.md) | End-to-end example in under 5 minutes |
| [Querying](querying.md) | `select()`, filters, sort, pagination, `ScalarResult` |
| [Session](session.md) | Session lifecycle, writes, flush vs commit |
| [Migration Guide](migration-v0.2-to-v0.3.md) | Breaking changes from v0.2.0 |
| [Design](design.md) | Architecture rationale |
