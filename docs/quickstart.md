# Quickstart

End-to-end example: define a model, connect to MongoDB, and perform CRUD operations.

## 1. Install

```bash
pip install mongotic
```

## 2. Define a model

```python
from typing import Optional, Text

from pydantic import Field

from mongotic.model import MongoBaseModel


class User(MongoBaseModel):
    __databasename__ = "myapp"   # MongoDB database name
    __tablename__    = "users"   # MongoDB collection name

    name:    Text          = Field(..., max_length=50)
    email:   Text          = Field(...)
    company: Optional[Text] = Field(None)
    age:     Optional[int]  = Field(None, ge=0, le=200)
```

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
