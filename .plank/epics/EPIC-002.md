---
id: EPIC-002
title: "v0.4.0 - SA v2 API Completeness"
status: done
created: 2026-03-03
updated: 2026-03-06
issues:
  - MGT-008
  - MGT-018
  - MGT-019
  - MGT-020
  - MGT-021
  - MGT-022
  - MGT-023
  - MGT-024
  - MGT-025
  - MGT-026
  - MGT-027
---

# EPIC-002: v0.4.0 — SA v2 API Completeness

## Goal

Fill the remaining gaps between mongotic and SQLAlchemy v2's commonly used ORM
APIs. After v0.3.x delivered the core `select()` / `session.scalars()` pattern,
v0.4.0 focuses on **query expressiveness** (logical operators, string matching,
null checks) and **session completeness** (refresh, merge, state inspection,
iteration).

## Definition of Done

v0.4.0 is considered complete when:

- [x] `or_()`, `and_()`, `not_()` logical combinators work in `.where()` clauses
- [x] `.is_(None)` / `.is_not(None)` null checks work
- [x] `.like()`, `.contains()`, `.startswith()`, `.endswith()` string operators work
- [x] `.between(low, high)` range operator works
- [x] `.distinct()` returns unique values for a field
- [x] `ScalarResult` supports `__iter__` / `__next__` for direct iteration
- [x] `session.refresh(instance)` reloads from DB
- [x] `session.merge(instance)` performs upsert
- [x] `session.dirty` / `session.new` / `session.deleted` properties exposed
- [x] `__indexes__` declarative index definition works
- [x] Documentation updated for all new APIs
- [x] All tests pass

## Implementation Phases

### Phase 1 — Query Logic Foundation (sequential: MGT-018 → MGT-019)

The logical combinators are the most impactful missing piece. Null operators
follow naturally and can leverage `not_()` for `.is_not(None)`.

| ID | Title |
|----|-------|
| MGT-018 | `or_()`, `and_()`, `not_()` logical combinators |
| MGT-019 | `.is_(None)` / `.is_not(None)` null operators |

### Phase 2 — Extended Query Operators (depend on Phase 1; can parallelize)

String operators, range checks, and distinct queries. These may use `not_()`
for negated variants.

| ID | Title |
|----|-------|
| MGT-022 | `.like()`, `.contains()`, `.startswith()`, `.endswith()` string operators |
| MGT-023 | `.between()` range operator |
| MGT-024 | `.distinct()` on Select |

### Phase 3 — Session & Result Enhancements (independent of Phase 1-2; can parallelize)

Improve the session and result interfaces to match SA v2 expectations.

| ID | Title |
|----|-------|
| MGT-020 | ScalarResult `__iter__` / `__next__` iteration |
| MGT-021 | `session.refresh(instance)` |
| MGT-025 | `session.merge(instance)` upsert |
| MGT-026 | Session state properties `.dirty` / `.new` / `.deleted` |

### Phase 4 — Schema & DDL (independent; can parallelize with Phase 2-3)

| ID | Title |
|----|-------|
| MGT-008 | Model `__indexes__` definition |

### Phase 5 — Docs & Release

| ID | Title |
|----|-------|
| MGT-027 | v0.4.0 documentation update |

## Deferred to v0.5.0

| ID | Title | Reason |
|----|-------|--------|
| MGT-028 | Column projection | Requires new return type design |
| MGT-029 | `session.expunge()` / `session.expire()` | Lower priority session management |
| MGT-030 | `.yield_per()` / `.partitions()` streaming | Requires cursor lifecycle changes |
