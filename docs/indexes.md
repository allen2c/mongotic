# Indexes

mongotic supports two complementary ways to declare indexes:

1. **`__indexes__` class attribute** — list pymongo `IndexModel` entries
   directly. Best for compound, full-text, geospatial, or any
   pymongo-specific index option.
2. **Per-field shorthand on `mapped_field()`** — pass `index=True`,
   `unique=True`, and/or `sparse=True` on the field declaration itself for
   simple single-field indexes.

Both forms can be combined on the same model and are applied by the same
`create_indexes()` call.

## Declaring indexes on a model

```python
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from mongotic import Mapped, MongoBaseModel, mapped_field

class User(MongoBaseModel):
    __databasename__ = "mydb"
    __tablename__ = "users"
    __indexes__ = [
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("created_at", DESCENDING)]),
    ]

    email:      Mapped[str] = mapped_field()
    name:       Mapped[str] = mapped_field()
    created_at: Mapped[int] = mapped_field()
```

`__indexes__` is a class-level attribute and does **not** appear in `model_dump()` or Pydantic's field schema.

Models without `__indexes__` default to an empty list — no indexes are created beyond MongoDB's built-in `_id` index.

---

## Applying indexes with `create_indexes()`

Indexes are **not** created automatically. Call `create_indexes()` explicitly — typically once at application startup.

```python
from mongotic import create_engine, create_indexes

engine = create_engine("mongodb://localhost:27017")

create_indexes(engine, User)
```

Multiple models can be passed in a single call:

```python
create_indexes(engine, User, Post, Comment)
```

`create_indexes()` is idempotent — calling it multiple times on the same collection is safe. It calls pymongo's `collection.create_indexes()` under the hood.

---

## Compound and multi-key indexes

`IndexModel` supports all pymongo index options:

```python
from pymongo import ASCENDING, TEXT
from pymongo.operations import IndexModel

class Article(MongoBaseModel):
    __databasename__ = "mydb"
    __tablename__ = "articles"
    __indexes__ = [
        # Compound index
        IndexModel([("author_id", ASCENDING), ("created_at", ASCENDING)]),
        # Full-text search index
        IndexModel([("title", TEXT), ("body", TEXT)]),
        # Sparse unique index
        IndexModel([("slug", ASCENDING)], unique=True, sparse=True),
    ]
```

Refer to the [pymongo IndexModel documentation](https://pymongo.readthedocs.io/en/stable/api/pymongo/operations.html#pymongo.operations.IndexModel) for the full list of options.

---

## Per-field shorthand

For straightforward single-field indexes you can declare the intent on the
field itself with `mapped_field()` — no need to write a separate `IndexModel`.

```python
from mongotic import Mapped, MongoBaseModel, mapped_field

class User(MongoBaseModel):
    __databasename__ = "mydb"
    __tablename__ = "users"

    email: Mapped[str]  = mapped_field(unique=True, index=True)
    slug:  Mapped[str | None] = mapped_field(default=None, unique=True, sparse=True)
    name:  Mapped[str]  = mapped_field(index=True)
```

The `index` / `unique` / `sparse` flags survive on
`User.model_fields["email"]` as attributes of the `MongoFieldInfo` Pydantic
descriptor, so tooling that introspects model fields (e.g. schema generators)
can read them directly. Reach for `__indexes__` when you need anything beyond
single-field options — compound keys, text indexes, geo indexes, partial
filter expressions, etc.
