# Session

## Creating a session factory

```python
from mongotic import create_engine
from mongotic.orm import sessionmaker

engine  = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)
```

`sessionmaker` returns a class. Call it to open a session:

```python
session = Session()
```

---

## Context manager (recommended)

```python
with Session() as session:
    session.add(User(name="Alice", email="alice@example.com"))
    session.commit()
# session.close() is called automatically on exit
```

On exit, `close()` discards any un-flushed staged changes.

---

## Writing

### `add(instance)` and `add_all(instances)`

Stage one or more new documents for insertion. The document is **not** written to MongoDB until you call `flush()` or `commit()`.

```python
session.add(User(name="Alice", email="alice@example.com"))
session.add_all([
    User(name="Bob",   email="bob@example.com"),
    User(name="Carol", email="carol@example.com"),
])
session.commit()
```

### `delete(instance)`

Stage an existing document for deletion. Requires the instance to have a valid `_id`.

```python
user = session.scalars(select(User).where(User.email == "bob@example.com")).first()
session.delete(user)
session.commit()
```

### Field assignment (auto-tracking)

Assigning a field on an instance that is already attached to a session automatically stages an update:

```python
user = session.scalars(select(User).where(User.email == "alice@example.com")).first()
user.company = "Acme"   # staged automatically
session.commit()        # writes the $set to MongoDB
```

---

## flush() vs commit()

| | `flush()` | `commit()` |
|-|-----------|------------|
| What it does | Writes all staged ops to MongoDB immediately | Alias for `flush()` |
| After the call | `_id` is available on inserted instances | Same |
| Can be undone? | **No** — changes are persisted | **No** |

```python
with Session() as session:
    new_user = User(name="Dave", email="dave@example.com")
    session.add(new_user)
    session.flush()
    print(new_user._id)   # ObjectId string is now available
    session.commit()      # no-op if nothing else was staged
```

!!! note "No multi-document transactions"
    mongotic does **not** wrap writes in MongoDB transactions. Each document write is individually atomic, but cross-document atomicity is not guaranteed. See [Design](design.md) for the rationale.

---

## rollback()

Discards staged (not yet flushed) changes. It **cannot** undo writes already sent to MongoDB.

```python
session.add(User(name="Temp"))
session.rollback()   # "Temp" user is never written
```

---

## close()

Discards un-flushed staged changes and is called automatically by the context manager. Equivalent to `rollback()` followed by releasing the session.

---

## refresh(instance)

Reloads all fields of an instance from the database in-place. Useful after an external process has modified the document, or to confirm the current DB state.

```python
with Session() as session:
    user = session.scalars(select(User).where(User.name == "Alice")).one()
    print(user.age)  # 25

    # some external process updates the document...

    session.refresh(user)
    print(user.age)  # 30 — reloaded from DB
```

- Raises `ValueError` if the instance has no `_id` (was never persisted).
- Raises `NotFound` if the document no longer exists in the database.
- Clears any pending field-level updates for the instance after refresh.

---

## merge(instance)

Stages an instance for an upsert on the next `flush()` / `commit()`. If `_id` is already set, the existing document is replaced; if not, a new document is inserted.

```python
with Session() as session:
    # If a user with this _id exists → update; otherwise → insert
    user = User(name="Alice", age=30)
    user._id = "507f1f77bcf86cd799439011"   # _id is a private attr, set after construction
    merged = session.merge(user)
    session.flush()

    print(merged._id)  # "507f1f77bcf86cd799439011"
```

| Scenario | Behaviour |
|---|---|
| `instance._id` is set and document exists | Replaces document on flush |
| `instance._id` is set but document doesn't exist | Inserts document on flush |
| `instance._id` is `None` | Behaves like `session.add()` |

!!! note
    `merge()` uses MongoDB's `replace_one(..., upsert=True)` under the hood. Any pending field-level updates for the same instance are discarded — the full in-memory state is written on flush.

---

## Session state properties

Inspect the session's pending state before flushing:

```python
with Session() as session:
    user = User(name="Alice", age=25)
    session.add(user)

    print(session.new)      # [User(name="Alice", ...)]
    print(session.dirty)    # []
    print(session.deleted)  # []

    session.flush()

    user.age = 26
    print(session.dirty)    # [User(name="Alice", age=26)]

    session.delete(user)
    print(session.deleted)  # [User(name="Alice", ...)]
```

| Property | Returns | Description |
|---|---|---|
| `session.new` | `list[Model]` | Instances staged for insertion |
| `session.dirty` | `list[Model]` | Instances with pending field changes |
| `session.deleted` | `list[Model]` | Instances staged for deletion |

All three properties return shallow copies — mutating the returned list does not affect session state. All are empty after `flush()`.
