# Azure Cosmos DB Compatibility

mongotic is verified against **Azure Cosmos DB for MongoDB (vCore / RU serverless)** with
both `pymongo 4.10` (Cosmos's officially recommended pin) and the latest `pymongo 4.x`.
This page records what works, what does not, and how to work around the gaps.

## Supported

The following features pass against Cosmos for MongoDB:

- Sync and async clients (`pymongo.MongoClient`, `pymongo.AsyncMongoClient`)
- All CRUD operations (`insert_one`, `find`, `update_one`, `delete_one`, …)
- Session lifecycle, `add` / `flush` / `commit` / `rollback`
- `session.merge`, `session.refresh`, identity-map state transitions
- Query operators: `$and`, `$or`, `$not`, `$in`, `$nin`, `$regex`, `$exists`,
  `$gt/$gte/$lt/$lte`, `$between`, `$null`-style checks
- Projection and `distinct`
- `find` cursors and `Result` iteration (sync + async)

## Known limitations

The following operations are rejected by Cosmos. mongotic itself works correctly;
the limits are imposed by the Cosmos for MongoDB API.

### 1. Unique indexes cannot be added to an existing collection

```text
Forbidden (403): The unique index cannot be modified.
To change the unique index, remove the collection and re-create a new one.
```

Cosmos requires unique indexes to be declared **at container creation time** via the
Cosmos Data Plane (Azure CLI, Bicep/ARM, or the Cosmos SDK). Calling
`create_indexes(engine, Model)` against a Cosmos container that already exists
will fail if any index in `__indexes__` is `unique=True`.

**Workarounds**

- Pre-create the container with the unique index using Azure tooling, then point
  mongotic at it. mongotic's runtime behavior (duplicate detection, errors raised
  on conflict) works normally once the index exists.
- Drop and recreate the container if you need to change unique-index keys.

### 2. `order_by` requires the field to be in the indexing policy

```text
BadRequest (400): The index path corresponding to the
specified order-by item is excluded.
```

Cosmos only sorts on fields covered by the container's indexing policy. By default
Cosmos indexes most paths, but custom indexing policies can exclude some — and any
excluded path cannot be used in `select(...).order_by(field)`.

**Workarounds**

- Ensure the field appears in the Cosmos container's indexing policy (it usually
  does by default; check if you have customized it).
- For ad-hoc sorting you cannot index, fetch unsorted then sort in Python.

## Running the test suite against Cosmos

The suite auto-skips the known-incompatible tests when it detects a Cosmos URI:

```bash
MONGODB_URI="<your-cosmos-connection-string>" pytest
```

Detection looks for `cosmos` or `documents.azure.com` in `MONGODB_URI`. The eight
known-incompatible tests are tagged with `@pytest.mark.cosmos_unsupported` and will
show as skipped, not failed.

## Compatibility matrix

| Feature                                       | Cosmos | Notes                                |
| --------------------------------------------- | :----: | ------------------------------------ |
| Sync + async clients                          |   ✅   | pymongo 4.10+ (Cosmos pin) verified  |
| CRUD                                          |   ✅   |                                      |
| Session lifecycle / merge / refresh / state   |   ✅   |                                      |
| Logical / comparison / null / regex operators |   ✅   |                                      |
| Projection / distinct                         |   ✅   |                                      |
| Cursor iteration (sync + async)               |   ✅   |                                      |
| Adding unique index to existing collection    |   ❌   | Must declare at container-create time |
| `order_by` on non-indexed field               |   ❌   | Add field to indexing policy         |
