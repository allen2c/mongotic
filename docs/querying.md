# Querying

## Building a statement with `select()`

```python
from mongotic import select

stmt = select(User)
```

All clauses return the same `Select` object, so you can chain them:

```python
stmt = (
    select(User)
    .where(User.age >= 18)
    .order_by(-User.age)   # descending
    .limit(10)
    .offset(0)
)
```

### `.where(*conditions)`

Combine multiple conditions with repeated `.where()` calls — they are ANDed together.

| Expression | MongoDB equivalent |
|---|---|
| `User.age == 30` | `{"age": {"$eq": 30}}` |
| `User.age != 30` | `{"age": {"$ne": 30}}` |
| `User.age > 18` | `{"age": {"$gt": 18}}` |
| `User.age >= 18` | `{"age": {"$gte": 18}}` |
| `User.age < 65` | `{"age": {"$lt": 65}}` |
| `User.age <= 65` | `{"age": {"$lte": 65}}` |
| `User.role.in_(["admin", "mod"])` | `{"role": {"$in": [...]}}` |
| `User.role.not_in(["banned"])` | `{"role": {"$nin": [...]}}` |

```python
stmt = select(User).where(User.age >= 18, User.company == "Acme")
```

### `.order_by(*fields)`

Pass a `ModelField` for ascending, or negate it (`-User.field`) for descending:

```python
# ascending by name
stmt = select(User).order_by(User.name)

# descending by age, then ascending by name
stmt = select(User).order_by(-User.age, User.name)
```

### `.limit(n)` and `.offset(n)`

```python
stmt = select(User).limit(20).offset(40)   # page 3 of 20
```

---

## Executing with `session.scalars()`

```python
result = session.scalars(stmt)   # returns ScalarResult
```

`ScalarResult` is lazy — no MongoDB query is issued until you call a terminal method.

### Terminal methods

| Method | Returns | Behaviour |
|--------|---------|-----------|
| `.all()` | `list[Model]` | All matching documents |
| `.first()` | `Model \| None` | First match, or `None` |
| `.one()` | `Model` | Exactly one result; raises `NotFound` or `MultipleResultsFound` |
| `.one_or_none()` | `Model \| None` | One or `None`; raises `MultipleResultsFound` if 2+ |
| `.count()` | `int` | Number of matching documents |
| `.exists()` | `bool` | `True` if at least one document matches |

```python
users  = session.scalars(select(User)).all()
first  = session.scalars(select(User).where(User.age > 50)).first()
count  = session.scalars(select(User).where(User.company == "Acme")).count()
exists = session.scalars(select(User).where(User.company == "Acme")).exists()
```

### Strict single-result fetch

```python
from mongotic import NotFound, MultipleResultsFound

try:
    user = session.scalars(
        select(User).where(User.email == "alice@example.com")
    ).one()
except NotFound:
    ...   # 0 results
except MultipleResultsFound:
    ...   # 2+ results

# Returns None on 0 results; raises on 2+
user = session.scalars(
    select(User).where(User.email == "alice@example.com")
).one_or_none()
```

---

## Primary key lookup with `session.get()`

```python
user = session.get(User, "507f1f77bcf86cd799439011")
# returns User instance, or None if not found
```

---

## Bulk update and delete

```python
from mongotic import update, delete

# Update all guests to members — returns number of modified documents
modified = session.execute(
    update(User).where(User.role == "guest").values(role="member")
)

# Delete inactive users — returns number of deleted documents
deleted = session.execute(
    delete(User).where(User.active == False)
)
```

`session.execute()` runs immediately — no staging, no `commit()` needed.
