# Quickstart

End-to-end example: define a model, connect to MongoDB, and perform CRUD operations.

## 1. Install

```bash
pip install mongotic
```

## 2. Define a model

```python
from typing import Optional

from mongotic import Mapped, MongoBaseModel, mapped_field


class User(MongoBaseModel):
    __databasename__ = "myapp"   # MongoDB database name
    __tablename__    = "users"   # MongoDB collection name

    name:    Mapped[str]           = mapped_field(max_length=50)
    email:   Mapped[str]           = mapped_field()
    company: Mapped[Optional[str]] = mapped_field(default=None)
    age:     Mapped[Optional[int]] = mapped_field(default=None, ge=0, le=200)
```

!!! tip "Why `Mapped[T]` and not plain `Field()`?"
    `Mapped[T]` is what makes IDE / pyright recognise `User.name == "x"` as a
    query expression instead of a `bool`, and what lets `.in_()`, `.like()`,
    `.between()`, and friends work without type warnings. See the
    [migration guide](migration-v0.5-to-v0.6.md) for the rationale.

    `mapped_field()` accepts every keyword Pydantic's `Field()` accepts (it
    subclasses `pydantic.fields.FieldInfo`), plus three Mongo-specific extras:
    `index=`, `unique=`, and `sparse=`.

## 3. Connect

```python
from mongotic import create_engine
from mongotic.orm import sessionmaker

engine  = create_engine("mongodb://localhost:27017")
Session = sessionmaker(bind=engine)
```

`create_engine` returns a standard `pymongo.MongoClient` — any connection string pymongo accepts works here.

## 4. Write

```python
with Session() as session:
    session.add(User(name="Alice", email="alice@example.com", age=30))
    session.add_all([
        User(name="Bob",   email="bob@example.com",   age=25),
        User(name="Carol", email="carol@example.com", age=28),
    ])
    session.commit()   # writes to MongoDB immediately
```

After `commit()`, each instance's `_id` field is populated with the MongoDB ObjectId string.

## 5. Query

```python
from mongotic import select

with Session() as session:
    # All users
    users = session.scalars(select(User)).all()

    # Filtered
    adults = session.scalars(select(User).where(User.age >= 18)).all()

    # First match (returns None if not found)
    alice = session.scalars(
        select(User).where(User.email == "alice@example.com")
    ).first()

    # By primary key
    user = session.get(User, alice._id)
```

## 6. Update

```python
with Session() as session:
    alice = session.scalars(
        select(User).where(User.email == "alice@example.com")
    ).first()
    alice.company = "Acme"   # change is tracked automatically
    session.commit()
```

## 7. Delete

```python
with Session() as session:
    alice = session.scalars(
        select(User).where(User.email == "alice@example.com")
    ).first()
    session.delete(alice)
    session.commit()
```

## Next steps

- [Querying](querying.md) — filters, sort, pagination, count, exists
- [Session](session.md) — flush vs commit, rollback, context manager

---

## Async quickstart

If your application runs inside an `asyncio` event loop, use `mongotic.asyncio` instead. The API mirrors the sync version exactly.

```python
import asyncio
from mongotic.asyncio import create_async_engine, async_sessionmaker
from mongotic import insert, select

async_engine = create_async_engine("mongodb://localhost:27017")
AsyncSession  = async_sessionmaker(bind=async_engine)

async def main():
    async with AsyncSession() as session:
        # Bulk insert
        await session.execute(
            insert(User).values([
                {"name": "Alice", "email": "alice@example.com", "age": 30},
                {"name": "Bob",   "email": "bob@example.com",   "age": 25},
            ])
        )

        # Query
        adults = await session.scalars(select(User).where(User.age >= 18)).all()
        print([u.name for u in adults])

        # Async iteration
        async for user in session.scalars(select(User)):
            print(user.name)

asyncio.run(main())
```

See [Async](async.md) for the full reference — session lifecycle, projection, indexes, and a sync/async cheat sheet.
