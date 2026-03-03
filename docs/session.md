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
