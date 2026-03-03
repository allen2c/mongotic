---
id: EPIC-001
title: "v0.3.0 - SQLAlchemy v2 Alignment (Breaking Change)"
status: done
created: 2026-03-03
updated: 2026-03-03  # All phases complete
issues:
  - MGT-001
  - MGT-012
  - MGT-009
  - MGT-010
  - MGT-011
  - MGT-004
  - MGT-002
  - MGT-003
  - MGT-005
  - MGT-006
  - MGT-007
  - MGT-013
---

# EPIC-001: v0.3.0 - SQLAlchemy v2 Alignment (Breaking Change)

## Goal

Refactor mongotic's session and query interface to align with SQLAlchemy v2
semantics. The old `session.query()` API is removed in favour of `select()` +
`session.scalars()`. This is a deliberate, documented breaking change.

## Definition of Done

v0.3.0 is considered complete when:

- [x] `session.query()` no longer exists
- [x] `select(Model).where(...).order_by(...).limit(...).offset(...)` works
- [x] `session.scalars(stmt)` returns a `ScalarResult`
- [x] `ScalarResult` has: `.all()`, `.first()`, `.one()`, `.one_or_none()`, `.count()`, `.exists()`
- [x] `session.get(Model, id)` returns instance or `None`
- [x] `session.flush()` writes staged ops and makes `_id` available
- [x] `session.rollback()` discards staged (not yet flushed) changes
- [x] No MongoDB transaction dependency (works on standalone)
- [x] `session.add_all([...])` works
- [x] All known bugs in `_commit` and `__setattr__` tracking are fixed
- [x] All tests pass under the new API
- [x] `update()` and `delete()` statement builders work via `session.execute()` (Phase 3)
- [x] Migration guide from v0.2.0 is written (Phase 4)

## Design Decisions

### No multi-document transaction support

MongoDB transactions require a replica set or mongos.  Because `mongotic`
targets both standalone dev instances and production replica sets, we do
**not** wrap writes in MongoDB transactions.

Consequences:

- Each individual document write is atomic (guaranteed by MongoDB).
- **Cross-document atomicity is not guaranteed** — if you need all-or-nothing
  across multiple documents, run your own replica set and manage sessions
  manually via pymongo.
- `flush()` writes staged ops immediately to MongoDB.  After `flush()` the
  writes are **persisted** — they cannot be undone by `rollback()`.
- `rollback()` discards only *staged but not yet flushed* changes.
- `commit()` is an alias for `flush()` (kept for SA v2 API familiarity).

This decision may be revisited in a future version.

## New API Contract

```python
from mongotic import create_engine, select, update, delete
from mongotic.orm import sessionmaker

engine  = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)

with Session() as session:
    # Query
    stmt  = select(User).where(User.age > 18).order_by(-User.created_at).limit(10)
    users = session.scalars(stmt).all()           # List[User]
    user  = session.scalars(stmt).first()         # User | None
    user  = session.scalars(stmt).one()           # User (raises if 0 or 2+)
    user  = session.scalars(stmt).one_or_none()   # User | None (raises if 2+)
    count = session.scalars(stmt).count()         # int
    flag  = session.scalars(stmt).exists()        # bool

    # PK lookup
    user = session.get(User, "507f1f77bcf86cd799439011")  # User | None

    # Write
    session.add(User(name="Alice", age=25))
    session.add_all([User(name="Bob"), User(name="Carol")])
    session.flush()    # write staged ops to DB immediately; _id is available after
    session.commit()   # alias for flush()

    # Discard staged (not yet flushed) changes
    session.rollback()

    # Bulk
    session.execute(update(User).where(User.role == "guest").values(role="member"))
    session.execute(delete(User).where(User.active == False))
```

## Implementation Phases

### Phase 0 — Pre-work (independent, can parallelize)
| ID | Title |
|----|-------|
| MGT-001 | Sync version.py to 0.3.0 |
| MGT-012 | Fix existing bugs in ORM |

### Phase 1 — Core Architecture (sequential: 009 → 010 → 011)
| ID | Title |
|----|-------|
| MGT-009 | Select statement builder |
| MGT-010 | ScalarResult class |
| MGT-011 | Refactor Session to SA v2 |

### Phase 2 — API Completeness (all depend on Phase 1, can parallelize)
| ID | Title |
|----|-------|
| MGT-004 | Select.order_by() |
| MGT-002 | ScalarResult.count() |
| MGT-003 | ScalarResult.exists() |
| MGT-005 | ScalarResult.one() + one_or_none() + MultipleResultsFound |

### Phase 3 — Bulk Operations (depend on Phase 1, can parallelize)
| ID | Title |
|----|-------|
| MGT-006 | update() statement via session.execute() |
| MGT-007 | delete() statement via session.execute() |

### Phase 4 — Docs & Release
| ID | Title |
|----|-------|
| MGT-013 | SA v2 alignment documentation + migration guide |

## Deferred to v0.4.0

| ID | Title | Reason |
|----|-------|--------|
| MGT-008 | Model __indexes__ | Independent of SA v2 alignment; lower priority |
