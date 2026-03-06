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

## Logical combinators

Use `or_()`, `and_()`, and `not_()` to compose complex filter conditions.

```python
from mongotic import select, or_, and_, not_

# OR — users who are admin or moderator
stmt = select(User).where(
    or_(User.role == "admin", User.role == "moderator")
)

# NOT — exclude banned users
stmt = select(User).where(
    not_(User.status == "banned")
)

# Nested composition
stmt = select(User).where(
    and_(
        User.age >= 18,
        or_(User.role == "admin", User.verified == True),
    )
)

# not_(or_(...)) maps to MongoDB $nor
stmt = select(User).where(
    not_(or_(User.role == "guest", User.role == "anonymous"))
)
```

| Combinator | MongoDB operator |
|---|---|
| `or_(A, B)` | `{"$or": [A, B]}` |
| `and_(A, B)` | `{"$and": [A, B]}` |
| `not_(field_op)` | `{"field": {"$not": expr}}` |
| `not_(or_(A, B))` | `{"$nor": [A, B]}` |

---

## Null checks

Use `.is_()` and `.is_not()` to test for `None` (null / missing fields).

```python
# Find users with no email set
stmt = select(User).where(User.email.is_(None))

# Find users that have an email
stmt = select(User).where(User.email.is_not(None))
```

!!! note
    In MongoDB, `{"field": None}` matches documents where the field is `null` **or** where the field does not exist at all.

---

## String operators

| Method | SQL equivalent | MongoDB |
|---|---|---|
| `.like("Al%")` | `LIKE 'Al%'` | `{"$regex": "^Al.*$"}` |
| `.ilike("al%")` | `ILIKE 'al%'` | `{"$regex": "^al.*$", "$options": "i"}` |
| `.contains("gmail")` | `LIKE '%gmail%'` | `{"$regex": "gmail"}` |
| `.startswith("Al")` | `LIKE 'Al%'` | `{"$regex": "^Al"}` |
| `.endswith("son")` | `LIKE '%son'` | `{"$regex": "son$"}` |

```python
stmt = select(User).where(User.name.startswith("Al"))
stmt = select(User).where(User.email.contains("@gmail.com"))
stmt = select(User).where(User.name.ilike("alice"))
```

!!! warning "Index usage"
    MongoDB can use an index for regex queries only when the pattern is anchored with `^`. `.startswith()` and `.like("prefix%")` benefit from indexes; `.contains()` and `.endswith()` do not.

---

## Range operator

`.between(low, high)` is inclusive on both ends — equivalent to `field >= low AND field <= high`.

```python
stmt = select(User).where(User.age.between(18, 65))

# Works with dates
from datetime import datetime
stmt = select(Order).where(
    Order.created_at.between(datetime(2024, 1, 1), datetime(2024, 12, 31))
)
```

---

## Distinct values

`.distinct(field)` returns a list of unique values for a field, optionally filtered by `.where()`.

```python
# All unique roles
roles = session.scalars(select(User).distinct(User.role)).all()
# → ["admin", "member", "guest"]

# Distinct roles among active users
active_roles = session.scalars(
    select(User).where(User.active == True).distinct(User.role)
).all()
```

!!! note
    `.distinct()` uses MongoDB's `collection.distinct()` command, which returns plain values (not model instances). `.order_by()` and `.limit()` have no effect on distinct queries.

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

### Iteration

`ScalarResult` is iterable — you can use it directly in `for` loops, list comprehensions, and unpacking:

```python
result = session.scalars(select(User).where(User.active == True))

# for loop
for user in result:
    print(user.name)

# list comprehension
names = [u.name for u in session.scalars(stmt)]

# unpacking
first, second, *rest = session.scalars(stmt)
```

Each iteration creates a fresh cursor, so the same `ScalarResult` can be iterated multiple times.

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
