# Indexes

## Declaring indexes on a model

Define MongoDB indexes on a model class using the `__indexes__` class attribute. Each entry is a pymongo `IndexModel`.

```python
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from mongotic.model import MongoBaseModel

class User(MongoBaseModel):
    __databasename__ = "mydb"
    __tablename__ = "users"
    __indexes__ = [
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("created_at", DESCENDING)]),
    ]

    email: str
    name: str
    created_at: int
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
