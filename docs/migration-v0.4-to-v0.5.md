# Migration Guide: v0.4.0 → v0.5.0

v0.5.0 adds bulk-insert support, column projection, a full async API, and a handful of session-management helpers. There is **one breaking change**: `session.execute()` now returns a `Result` object instead of a raw integer.

---

## API changes at a glance

| Area | v0.4.0 | v0.5.0 |
|------|--------|--------|
| `session.execute(update/delete)` | returned `int` (row count) | returns `Result` (`.rowcount`, `.inserted_ids`) |
| `session.execute(insert(...).values([...]))` | not available | returns `Result` |
| `session.execute(select(Model.col, ...))` | not available | returns `SelectResult` (rows of `Row`) |
| `session.scalars(select(Model.col))` | not available | unwraps to plain values |
| `session.scalar(stmt)` | not available | returns first value or `None` |
| `session.expunge(instance)` | not available | detaches instance from session |
| `session.expire(instance)` | not available | marks instance stale (no lazy reload) |
| `Select.yield_per(n)` | not available | accepted, no-op |
| Async API | not available | `mongotic.asyncio` |

---

## Breaking: `session.execute()` now returns `Result`

In v0.4.0 `session.execute()` returned a plain `int` for `update()` and `delete()` statements.

```python
# v0.4.0
modified = session.execute(
    update(User).where(User.role == "guest").values(role="member")
)
print(modified)   # 3  (an integer)

deleted = session.execute(
    delete(User).where(User.active == False)
)
print(deleted)    # 5  (an integer)
```

In v0.5.0 the return value is a `Result` object. Access `.rowcount` for the count, and `.inserted_ids` for any inserted ObjectIds.

```python
# v0.5.0
from mongotic.result import Result

r = session.execute(
    update(User).where(User.role == "guest").values(role="member")
)
assert isinstance(r, Result)
print(r.rowcount)      # 3
print(r.inserted_ids)  # []  (empty for update/delete)

r = session.execute(
    delete(User).where(User.active == False)
)
print(r.rowcount)      # 5
```

**Migration:** replace bare uses of the returned integer with `.rowcount`.

```python
# before
if session.execute(delete(User).where(...)):
    ...

# after
if session.execute(delete(User).where(...)).rowcount:
    ...
```

---

## New: `insert()` statement builder

`insert()` is a new bulk-write statement that bypasses the session staging area and writes directly to MongoDB.

```python
from mongotic import insert

with Session() as session:
    r = session.execute(
        insert(User).values([
            {"name": "Alice", "email": "alice@example.com", "age": 30},
            {"name": "Bob",   "email": "bob@example.com",   "age": 25},
        ])
    )
    print(r.rowcount)       # 2
    print(r.inserted_ids)   # ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"]
```

!!! note "Write-through — does not appear in `session.new`"
    `insert()` writes immediately. Inserted instances are **not** added to the session identity map, so they will not appear in `session.new`, `.dirty`, or `.deleted`. Use `session.add()` / `session.add_all()` when you need change-tracking.

---

## New: column projection

Pass individual `ModelField` attributes to `select()` to retrieve a lightweight subset of fields. `session.execute()` returns a `SelectResult` whose items are `Row` objects.

```python
from mongotic.result import Row, SelectResult

result = session.execute(
    select(User.name, User.email).where(User.age >= 18)
)
assert isinstance(result, SelectResult)

for row in result.all():
    print(row.name, row.email)
    # row supports attribute, index, and key access
    print(row[0], row["name"])
```

For a **single-column** projection, `session.scalars()` unwraps each `Row` to a plain value:

```python
names = session.scalars(
    select(User.name).where(User.company == "Acme")
).all()
# → ["Alice", "Bob", "Carol"]
```

!!! note
    Passing multiple columns to `session.scalars()` raises `TypeError`. Use `session.execute()` for multi-column projections.

---

## New: `session.scalar()` shortcut

`session.scalar(stmt)` is equivalent to `session.scalars(stmt).first()`. It returns the first unwrapped value, or `None` if there are no results.

```python
age = session.scalar(
    select(User.age).where(User.email == "alice@example.com")
)
# → 30, or None if not found
```

Works with full-model selects too — equivalent to `session.scalars(select(User).where(...)).first()`.

---

## New: `session.expunge()` and `session.expire()`

### `expunge(instance)`

Detaches an instance from the session. Pending field-level updates for that instance are discarded.

```python
user = session.scalars(select(User).where(User.name == "Alice")).one()
user.age = 99           # staged as dirty
session.expunge(user)   # removed from dirty tracking
assert session.dirty == []
assert user._session is None
```

After expunging, you may freely modify the instance or pass it to another session.

### `expire(instance)`

Marks an instance as stale so that the session knows its in-memory state may no longer reflect the database. Pending updates for the instance are cleared.

```python
session.expire(user)
# user._expired is True; no reload happens immediately
```

!!! warning "No lazy reload"
    Unlike SQLAlchemy's ORM, `expire()` in mongotic does **not** trigger a database round-trip on the next attribute access. The stale flag is informational only. Call `session.refresh(user)` explicitly when you need the current DB state.

    This is intentional: mongotic supports both sync and async sessions. Lazy attribute fetching would require `await` in the async path, which is incompatible with Python attribute access syntax. Explicit `refresh()` is the uniform API in both modes.

---

## New: `Select.yield_per(n)`

`yield_per(n)` is accepted for API compatibility with SQLAlchemy v2 patterns. It is a chainable no-op.

```python
stmt = select(User).where(User.active == True).yield_per(100)
# Executes identically to select(User).where(User.active == True)
```

!!! note
    PyMongo cursors are already lazy and memory-efficient. `yield_per` has no effect on cursor behaviour.

---

## New: `mongotic.asyncio`

v0.5.0 ships a full async API that mirrors the sync session on top of `pymongo.AsyncMongoClient`. See **[Async](async.md)** for the complete guide.

```python
from mongotic.asyncio import create_async_engine, async_sessionmaker

async_engine = create_async_engine("mongodb://localhost:27017")
AsyncSession  = async_sessionmaker(bind=async_engine)

async with AsyncSession() as session:
    await session.execute(insert(User).values([...]))
    users = await session.scalars(select(User)).all()
```

---

## What did NOT change

- Model definition (`MongoBaseModel`, `__databasename__`, `__tablename__`, `__indexes__`) — unchanged.
- `session.add()`, `session.add_all()`, `session.delete()` — unchanged.
- `session.flush()`, `session.commit()`, `session.rollback()`, `session.close()` — unchanged.
- `session.get(Model, id)` — unchanged.
- `session.refresh(instance)`, `session.merge(instance)` — unchanged.
- `session.scalars(select(Model).where(...))` — unchanged.
- All `select()` clauses (`.where()`, `.order_by()`, `.limit()`, `.offset()`, `.distinct()`) — unchanged.
- Context manager pattern — unchanged.
