# Migration Guide: v0.2.0 → v0.3.0

v0.3.0 aligns mongotic's API with SQLAlchemy v2 semantics. `session.query()` is **removed**. This is a deliberate, documented breaking change.

---

## API changes at a glance

| v0.2.0 | v0.3.0 |
|--------|--------|
| `session.query(User).filter(...)` | `session.scalars(select(User).where(...))` |
| `.filter()` / `.filter_by()` | `.where()` |
| `.first()` raised `NotFound` on 0 results | `.first()` returns `None` |
| `.all()` had a default limit of 5 | No default limit — returns all matches |
| No `.count()` / `.exists()` | `ScalarResult` has `.count()` and `.exists()` |
| No bulk operations | `update()` / `delete()` via `session.execute()` |

---

## Step-by-step migration

### Queries

```python
# v0.2.0
users = session.query(User).filter(User.age > 18).all()

# v0.3.0
users = session.scalars(select(User).where(User.age > 18)).all()
```

### First result

```python
# v0.2.0 — raises NotFound if no result
user = session.query(User).filter(User.email == "x@example.com").first()

# v0.3.0 — returns None if no result
user = session.scalars(select(User).where(User.email == "x@example.com")).first()
if user is None:
    ...
```

### Strict single-result fetch

```python
# v0.3.0 only
from mongotic import NotFound, MultipleResultsFound

try:
    user = session.scalars(select(User).where(User.email == "x@example.com")).one()
except NotFound:
    ...
except MultipleResultsFound:
    ...
```

### Sorting

```python
# v0.2.0
users = session.query(User).order_by("-age").all()

# v0.3.0  (use -ModelField for descending)
users = session.scalars(select(User).order_by(-User.age)).all()
```

### Count and existence

```python
# v0.3.0 only
count  = session.scalars(select(User).where(User.company == "Acme")).count()
exists = session.scalars(select(User).where(User.company == "Acme")).exists()
```

### Bulk operations

```python
# v0.3.0 only
from mongotic import update, delete

session.execute(update(User).where(User.role == "guest").values(role="member"))
session.execute(delete(User).where(User.active == False))
```

---

## What did NOT change

- Model definition (`MongoBaseModel`, `__databasename__`, `__tablename__`) — unchanged.
- `session.add()`, `session.add_all()`, `session.delete()` — unchanged.
- `session.flush()`, `session.commit()`, `session.rollback()` — unchanged.
- `session.get(Model, id)` — unchanged.
- Context manager pattern — unchanged.
