# Design

## Why SQLAlchemy v2 semantics?

### Statement / Result separation

SQLAlchemy v2 separates *building a query* from *executing it*:

```python
stmt   = select(User).where(User.age > 18)   # just a value — no I/O
result = session.scalars(stmt)               # execute against the DB
users  = result.all()                        # materialise results
```

This makes queries composable, testable, and readable. mongotic adopts the same pattern — `Select`, `Update`, and `Delete` objects carry no side-effects until they are passed to a `Session` method.

### Familiarity

Developers who already know SQLAlchemy v2 can use mongotic without learning a new query language. The surface area is intentionally small: `select`, `update`, `delete`, `session.scalars`, `session.execute`, `ScalarResult`.

---

## No multi-document transaction support

MongoDB transactions require a **replica set** or **mongos**. mongotic targets both standalone dev instances and production replica sets, so we do not wrap writes in MongoDB transactions.

Consequences:

- Each individual document write is atomic (MongoDB guarantee).
- **Cross-document atomicity is not guaranteed** — if you need all-or-nothing across multiple documents, manage sessions manually via pymongo.
- `flush()` / `commit()` writes staged ops immediately. After the call, changes are **persisted** and cannot be undone by `rollback()`.
- `rollback()` discards only *staged but not yet flushed* changes.

This decision may be revisited in a future version when replica set targeting is a first-class concern.

---

## Auto-tracking field mutations

`MongoBaseModel` uses a custom `__setattr__` hook. When an instance is attached to a session (i.e., loaded via `scalars()` or `get()`), any field assignment is automatically staged as an update:

```python
user = session.scalars(select(User).where(...)).first()
user.name = "New Name"   # staged — no explicit session.update() needed
session.commit()
```

This mirrors SQLAlchemy's unit-of-work pattern, where modified attributes are detected and flushed automatically.

---

## `commit()` is an alias for `flush()`

In SQLAlchemy, `commit()` finalises a transaction. mongotic has no transactions, so `commit()` is simply an alias for `flush()` — it writes all staged ops to MongoDB immediately. The alias exists for API familiarity and to ease migration from SQLAlchemy-backed codebases.
