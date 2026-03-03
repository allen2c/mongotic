---
id: EPIC-003
title: "v0.5.0 - Advanced Query & Session Management"
status: icebox
created: 2026-03-03
updated: 2026-03-03
issues:
  - MGT-028
  - MGT-029
  - MGT-030
---

# EPIC-003: v0.5.0 — Advanced Query & Session Management

## Goal

Add advanced query capabilities (column projection, streaming results) and
fine-grained session object management (expire, expunge). These are lower
priority SA v2 APIs that become valuable at scale.

## Definition of Done

v0.5.0 is considered complete when:

- [ ] Column projection via `select(User.name, User.email)` works
- [ ] `session.expunge(instance)` detaches an instance from the session
- [ ] `session.expire(instance)` marks instance for reload on next access
- [ ] `.yield_per(size)` enables batched cursor iteration
- [ ] `.partitions(size)` enables chunked result fetching
- [ ] Documentation updated
- [ ] All tests pass

## Implementation Phases

### Phase 1 — Query Enhancements

| ID | Title |
|----|-------|
| MGT-028 | Column projection |

### Phase 2 — Session Object Management

| ID | Title |
|----|-------|
| MGT-029 | `session.expunge()` / `session.expire()` |

### Phase 3 — Streaming & Batching

| ID | Title |
|----|-------|
| MGT-030 | `.yield_per()` / `.partitions()` streaming |
