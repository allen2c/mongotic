# Async API

## Overview

`mongotic.asyncio` is a full async session layer built on top of `pymongo.AsyncMongoClient`. It mirrors the sync `Session` API exactly — the same methods, the same statement builders, the same result types — so switching between sync and async code requires minimal changes.

Use the async API when your application already runs inside an `asyncio` event loop and you need non-blocking database I/O (e.g. FastAPI, Starlette, `asyncio.gather` workloads).

---

## Setup

```python
from mongotic.asyncio import create_async_engine, async_sessionmaker

async_engine = create_async_engine("mongodb://localhost:27017")
AsyncSessionLocal = async_sessionmaker(bind=async_engine)
```

`create_async_engine` returns a `pymongo.AsyncMongoClient` — any connection string pymongo accepts works here. `async_sessionmaker` returns a factory; call it to open a session:

```python
session = AsyncSessionLocal()
```

Or use the async context manager (recommended):

```python
async with AsyncSessionLocal() as session:
    ...
```

---

## Querying

### `session.scalars(stmt)` → `AsyncScalarResult`

Returns an `AsyncScalarResult`. Terminal methods are all `await`able:

```python
from mongotic import select

# All matching documents
users = await session.scalars(select(User).where(User.age >= 18)).all()

# First match or None
alice = await session.scalars(
    select(User).where(User.email == "alice@example.com")
).first()

# Exactly one result — raises NotFound or MultipleResultsFound
user = await session.scalars(
    select(User).where(User.email == "alice@example.com")
).one()

# One or None — raises MultipleResultsFound on 2+
user = await session.scalars(
    select(User).where(User.email == "alice@example.com")
).one_or_none()

# Count and existence
count  = await session.scalars(select(User).where(User.company == "Acme")).count()
exists = await session.scalars(select(User).where(User.company == "Acme")).exists()
```

### Async iteration

```python
async for user in session.scalars(select(User).where(User.active == True)):
    print(user.name)
```

### `session.scalar(stmt)` shortcut

Returns the first unwrapped value, or `None`:

```python
age = await session.scalar(
    select(User.age).where(User.email == "alice@example.com")
)
# → 30, or None if not found
```

### Column projection — `session.execute(select(Model.col, ...))`

Passing individual fields to `select()` returns an `AsyncSelectResult` whose rows are `Row` objects:

```python
from mongotic.asyncio import AsyncSelectResult
from mongotic.result import Row

result = await session.execute(
    select(User.name, User.age).where(User.age >= 18)
)
assert isinstance(result, AsyncSelectResult)

rows = await result.all()
for row in rows:
    print(row.name, row.age)
    # also: row[0], row["name"]
```

For a single-column projection, `session.scalars()` unwraps each row to a plain value:

```python
names = await session.scalars(
    select(User.name).where(User.company == "Acme")
).all()
# → ["Alice", "Bob", "Carol"]
```

### Primary key lookup

```python
user = await session.get(User, "507f1f77bcf86cd799439011")
# returns User instance, or None if not found
```

---

## Writing

### `session.add()` and `session.add_all()` (sync)

Staging is synchronous — no `await` needed:

```python
session.add(User(name="Alice", email="alice@example.com", age=30))
session.add_all([
    User(name="Bob",   email="bob@example.com",   age=25),
    User(name="Carol", email="carol@example.com", age=28),
])
await session.commit()
```

### `await session.commit()` and `await session.flush()`

Both flush all staged operations to MongoDB immediately:

```python
new_user = User(name="Dave", email="dave@example.com")
session.add(new_user)
await session.flush()
print(new_user._id)   # ObjectId string is now available
await session.commit()   # no-op if nothing else staged
```

### `session.rollback()` (sync)

Discards staged changes that have not yet been flushed:

```python
session.add(User(name="Temp"))
session.rollback()   # "Temp" is never written
```

### `await session.refresh(instance)`

Reloads all fields from the database in-place:

```python
user = await session.scalars(select(User).where(User.name == "Alice")).one()
# ... external process modifies the document ...
await session.refresh(user)
print(user.age)   # reloaded from DB
```

### `session.merge(instance)` (sync)

Stages an upsert — replaces the document on flush if `_id` is set, inserts otherwise:

```python
user = User(name="Alice", age=30)
user._id = "507f1f77bcf86cd799439011"
session.merge(user)
await session.commit()
```

### Field assignment (auto-tracking)

Field changes on attached instances are tracked automatically:

```python
user = await session.scalars(select(User).where(User.name == "Alice")).one()
user.age = 31           # staged as dirty
await session.commit()  # writes $set to MongoDB
```

---

## Bulk DML

All bulk operations use `await session.execute()` and return a `Result`:

```python
from mongotic import insert, update, delete
from mongotic.result import Result

# Bulk insert
r = await session.execute(
    insert(User).values([
        {"name": "Alice", "email": "alice@example.com", "age": 30},
        {"name": "Bob",   "email": "bob@example.com",   "age": 25},
    ])
)
print(r.rowcount)       # 2
print(r.inserted_ids)   # ["<id1>", "<id2>"]

# Bulk update
r = await session.execute(
    update(User).where(User.role == "guest").values(role="member")
)
print(r.rowcount)   # number of modified documents

# Bulk delete
r = await session.execute(
    delete(User).where(User.active == False)
)
print(r.rowcount)   # number of deleted documents
```

!!! note
    `insert()` does not add instances to the session's identity map. Bulk-inserted documents will not appear in `session.new`, `.dirty`, or `.deleted`.

---

## Session lifecycle

### Async context manager

```python
async with AsyncSessionLocal() as session:
    session.add(User(name="Alice", email="alice@example.com"))
    await session.commit()
# session.close() called automatically — un-flushed changes are discarded
```

### `session.expunge(instance)`

Detaches an instance from the session and discards any pending updates for it:

```python
user = await session.scalars(select(User).where(User.name == "Alice")).one()
user.age = 99
session.expunge(user)
assert session.dirty == []
assert user._session is None
```

The instance may be freely modified or re-added to a new session afterwards.

### `session.expire(instance)`

Marks an instance as stale. Pending field updates are cleared, but **no reload happens** — the attribute values remain as-is until you call `refresh()`.

```python
session.expire(user)
# user._expired is True; values still reflect the in-memory state
await session.refresh(user)   # explicit reload
```

!!! warning "No lazy reload"
    `expire()` does not trigger a database round-trip on attribute access. Call `refresh()` explicitly when you need the current DB state. See [Migration Guide](migration-v0.4-to-v0.5.md#new-sessionexpunge-and-sessionexpire) for the rationale.

### State inspection

```python
session.add(user)
print(session.new)      # [User(...)]
await session.commit()
user.age = 99
print(session.dirty)    # [User(...)]
session.delete(user)
print(session.deleted)  # [User(...)]
```

---

## Indexes

Use `create_async_indexes` to apply `__indexes__` declarations to MongoDB:

```python
from mongotic.asyncio import create_async_indexes
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel


class User(MongoBaseModel):
    __databasename__ = "myapp"
    __tablename__ = "users"
    __indexes__ = [
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("created_at", DESCENDING)]),
    ]
    ...


await create_async_indexes(async_engine, User)
# multiple models at once:
await create_async_indexes(async_engine, User, Post, Comment)
```

---

## Sync vs async cheat sheet

| Operation | Sync | Async |
|---|---|---|
| Open session | `Session()` | `AsyncSessionLocal()` |
| Context manager | `with Session() as s:` | `async with AsyncSessionLocal() as s:` |
| Stage insert | `s.add(obj)` *(sync)* | `s.add(obj)` *(sync)* |
| Commit / flush | `s.commit()` | `await s.commit()` |
| Rollback | `s.rollback()` *(sync)* | `s.rollback()` *(sync)* |
| Scalar query | `s.scalars(stmt).all()` | `await s.scalars(stmt).all()` |
| Async iteration | — | `async for obj in s.scalars(stmt):` |
| Scalar shortcut | `s.scalar(stmt)` | `await s.scalar(stmt)` |
| PK lookup | `s.get(Model, id)` | `await s.get(Model, id)` |
| Refresh | `s.refresh(obj)` | `await s.refresh(obj)` |
| Merge (upsert) | `s.merge(obj)` *(sync)* | `s.merge(obj)` *(sync)* |
| Bulk DML | `s.execute(stmt)` | `await s.execute(stmt)` |
| Expunge | `s.expunge(obj)` *(sync)* | `s.expunge(obj)` *(sync)* |
| Expire | `s.expire(obj)` *(sync)* | `s.expire(obj)` *(sync)* |
| Create indexes | `create_indexes(engine, *models)` | `await create_async_indexes(engine, *models)` |

---

## Caveats

**Sessions are not task-safe.** A single `AsyncSession` should not be shared across multiple concurrent `asyncio` tasks. Create one session per task (or per request in web frameworks).

**`expire()` does not lazy-reload.** After calling `session.expire(instance)`, the current attribute values remain in memory. The `_expired` flag is informational only. You must call `await session.refresh(instance)` explicitly to fetch the current database state.
