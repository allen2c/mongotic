# Migrating from v0.5 to v0.6

## What changed

Field declarations now use `Mapped[T] = mapped_field(...)` for full IDE and
pyright support of query operators (`.in_`, `.like`, `.between`, etc.).

## Why

In v0.5 and earlier, fields were declared with `name: str = Field(...)`. This
meant pyright saw `User.name` (class-level access) as `str`, so
`.where(User.name.in_(...))` generated a static-type error even though it
worked at runtime. The root cause: Python's type system does not surface
metaclass `__getattr__` for declared fields, and Pydantic v2's
`dataclass_transform` declares the field type identically at class and
instance level.

v0.6 introduces `Mapped[T]` — a generic descriptor that pyright sees as
`Mapped[T]` at the class level (with operators returning
`ModelFieldOperation`) and as `T` at the instance level (so
`user.name.upper()` still works as `str`).

## Migration recipe

Search and replace inside each model:

```python
# Before (v0.5)
from pydantic import Field
from mongotic.model import MongoBaseModel

class User(MongoBaseModel):
    __databasename__ = "myapp"
    __tablename__ = "users"

    name: str = Field(..., min_length=2)
    age: int = Field(0, ge=0, le=150)
    email: str | None = Field(None)
    tags: list[str] = Field(default_factory=list)
```

```python
# After (v0.6)
from mongotic import Mapped, MongoBaseModel, mapped_field

class User(MongoBaseModel):
    __databasename__ = "myapp"
    __tablename__ = "users"

    name: Mapped[str] = mapped_field(min_length=2)
    age: Mapped[int] = mapped_field(default=0, ge=0, le=150)
    email: Mapped[str | None] = mapped_field(default=None)
    tags: Mapped[list[str]] = mapped_field(default_factory=list)
```

### Substitution table

| v0.5 | v0.6 |
|---|---|
| `Field(...)` | `mapped_field()` |
| `Field(default)` | `mapped_field(default=default)` |
| `Field(default_factory=fn)` | `mapped_field(default_factory=fn)` |
| `Field(..., min_length=2)` | `mapped_field(min_length=2)` |
| `Field(default, ge=0, le=150)` | `mapped_field(default=default, ge=0, le=150)` |
| `Field(description="...")` | `mapped_field(description="...")` |
| `Field(alias="...")` | `mapped_field(alias="...")` |
| `from pydantic import Field` | `from mongotic import Mapped, mapped_field` |

## New Mongo extras

`mapped_field()` adds three Mongo-specific options that `Field()` does not
have:

- `index=True` — create a MongoDB index on this field at
  `create_indexes()` time.
- `unique=True` — uniqueness constraint on the index.
- `sparse=True` — sparse index.

```python
email: Mapped[str | None] = mapped_field(default=None, unique=True)
```

These propagate to `Model.model_fields[field_name]` as attributes on the
returned `MongoFieldInfo` (which itself is a subclass of Pydantic's
`FieldInfo`, so all standard Pydantic field metadata is preserved).

## Why this is backward compatible

Existing `Field()` declarations continue to work at runtime: the v0.6
metaclass installs a `Mapped` descriptor for every model field regardless of
how the field was declared. Class-level expressions like `User.name == "x"`
and `select(...).where(...)` will work the same way as in v0.5.

What changes:

1. Each legacy declaration emits a `DeprecationWarning` once at class
   creation time.
2. Pyright cannot infer `Mapped[T]` from a `str` annotation, so it will
   still warn at call sites that use methods like `.in_()` / `.like()` /
   `.between()` on legacy-declared fields. Switching to `Mapped[T]` is the
   only way to silence those warnings.

To suppress the deprecation warnings during a phased migration:

```python
import warnings
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"mongotic\..*",
)
```

The compatibility shim is **planned for removal in v0.7.0**. Plan to
complete migration before upgrading.

## Verification

Run pyright over your codebase and confirm the query-operator warnings are
gone:

```bash
pyright your_app/
```

Run your test suite:

```bash
pytest
```

If anything fails, check the
[v0.6 design spec](superpowers/specs/2026-05-28-v0.6.0-mapped-typing-design.md)
for the design rationale and any known limitations.

## What is and is not breaking

**Breaking:** None at runtime. Legacy declarations keep working; only a
warning is emitted.

**Behavioural changes:** None. Validation, serialization, JSON schema
generation, and ORM session semantics are identical to v0.5.

**Future breaking (v0.7.0):** Legacy `Field()` declarations on
`MongoBaseModel` subclasses will become an error.
