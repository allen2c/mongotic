from __future__ import annotations

import functools
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection

    from mongotic.query import Delete, Insert, Select, Update

from bson.objectid import ObjectId
from pymongo import AsyncMongoClient

from mongotic.exceptions import MultipleResultsFound, NotFound
from mongotic.model import (
    ModelFieldOperation,
    MongoBaseModel,
    _assert_model_bound,
)
from mongotic.result import Result, Row, SelectResult

_T = TypeVar("_T", bound=MongoBaseModel)


class AsyncScalarResult(Generic[_T]):
    def __init__(
        self,
        collection: "AsyncCollection[Dict[str, Any]]",
        stmt: "Select[_T]",
        model: Type[_T],
        session: "AsyncSession",
    ) -> None:
        self._collection = collection
        self._stmt = stmt
        self._model = model
        self._session = session

    def _is_projection(self) -> bool:
        return getattr(self._stmt, "is_projection", False)

    @functools.cached_property
    def _compiled_filter(self):
        return ModelFieldOperation.to_mongo_filter(filters=self._stmt._filters)

    def _build_cursor(self):
        from mongotic.query import _apply_cursor_modifiers

        if self._is_projection():
            field = self._stmt.projection_field_names[0]
            cursor = self._collection.find(
                self._compiled_filter, projection={field: 1, "_id": 0}
            )
        else:
            cursor = self._collection.find(self._compiled_filter)

        return _apply_cursor_modifiers(cursor, self._stmt)

    def _hydrate(self, doc_raw: Dict) -> _T:
        from mongotic.query import _hydrate_doc

        return _hydrate_doc(self._model, doc_raw, self._session)  # type: ignore[return-value]

    def _extract_value(self, doc):
        if self._is_projection():
            return doc.get(self._stmt.projection_field_names[0])
        return self._hydrate(doc)

    async def all(self) -> List[_T]:
        if self._stmt._distinct_field is not None:
            return await self._collection.distinct(  # type: ignore[return-value]
                self._stmt._distinct_field.field_name, self._compiled_filter
            )
        return [self._extract_value(doc) async for doc in self._build_cursor()]

    async def first(self) -> Optional[_T]:
        async for doc in self._build_cursor().limit(1):
            return self._extract_value(doc)
        return None

    async def one(self) -> _T:
        docs = [d async for d in self._build_cursor().limit(2)]
        if not docs:
            raise NotFound("No result found")
        if len(docs) > 1:
            raise MultipleResultsFound("Expected one result, got multiple")
        return self._extract_value(docs[0])

    async def one_or_none(self) -> Optional[_T]:
        docs = [d async for d in self._build_cursor().limit(2)]
        if not docs:
            return None
        if len(docs) > 1:
            raise MultipleResultsFound("Expected one result, got multiple")
        return self._extract_value(docs[0])

    async def count(self) -> int:
        return await self._collection.count_documents(self._compiled_filter)

    async def exists(self) -> bool:
        return (
            await self._collection.count_documents(self._compiled_filter, limit=1) > 0
        )

    async def __aiter__(self) -> AsyncIterator[_T]:
        async for doc in self._build_cursor():
            yield self._extract_value(doc)


class AsyncSelectResult(SelectResult):
    """Awaitable-terminal variant of SelectResult for column-projection queries."""

    def __init__(self, rows: List[Row]):
        super().__init__(rows)

    async def all(self) -> List[Row]:  # type: ignore[override]
        return super().all()

    async def first(self) -> Optional[Row]:  # type: ignore[override]
        return super().first()

    async def one(self) -> Row:  # type: ignore[override]
        return super().one()

    async def one_or_none(self) -> Optional[Row]:  # type: ignore[override]
        return super().one_or_none()

    async def __aiter__(self) -> AsyncIterator[Row]:
        for r in self._rows:
            yield r


class AsyncSession:
    def __init__(self, bind: Optional[AsyncMongoClient] = None) -> None:
        if bind is None:
            raise TypeError("AsyncSession requires bind=AsyncMongoClient")
        self.engine: AsyncMongoClient = bind
        self._add_instances: List[MongoBaseModel] = []
        self._update_instances: Dict[
            Tuple[int, str], Tuple[MongoBaseModel, str, Any]
        ] = {}
        self._delete_instances: List[MongoBaseModel] = []
        self._merge_instances: List[MongoBaseModel] = []

    # ── state properties ──────────────────────────────────────────────────────

    @property
    def new(self) -> List[MongoBaseModel]:
        return list(self._add_instances)

    @property
    def dirty(self) -> List[MongoBaseModel]:
        seen: Dict[int, MongoBaseModel] = {}
        for instance, _field, _value in self._update_instances.values():
            seen[id(instance)] = instance
        return list(seen.values())

    @property
    def deleted(self) -> List[MongoBaseModel]:
        return list(self._delete_instances)

    # ── querying ──────────────────────────────────────────────────────────────

    def scalars(self, stmt: "Select[_T]") -> AsyncScalarResult[_T]:
        from mongotic.query import Select

        if not isinstance(stmt, Select):
            raise TypeError(f"scalars() expects a Select statement, got {type(stmt)}")
        if getattr(stmt, "is_projection", False) and stmt.projection_field_count > 1:
            raise TypeError(
                "session.scalars() requires a single-column select; got multiple columns"
            )
        collection = self.engine[stmt._model.__databasename__][
            stmt._model.__tablename__
        ]
        return AsyncScalarResult(
            collection=collection,
            stmt=stmt,  # type: ignore[arg-type]
            model=stmt._model,
            session=self,
        )

    async def scalar(self, stmt: "Select[_T]") -> Optional[_T]:
        return await self.scalars(stmt).first()

    async def execute(
        self,
        stmt: "Union[Select[Any], Insert, Update, Delete]",
    ) -> Result:
        from mongotic.query import (
            Delete,
            Insert,
            Select,
            Update,
            _apply_cursor_modifiers,
        )

        collection = self.engine[stmt._model.__databasename__][
            stmt._model.__tablename__
        ]

        if isinstance(stmt, Select):
            if not stmt.is_projection:
                raise TypeError(
                    "session.execute(Select) requires column projection. "
                    "Use session.scalars(select(Model)) for full-model queries."
                )
            fields = stmt.projection_field_names
            filter_body = ModelFieldOperation.to_mongo_filter(filters=stmt._filters)
            projection = {name: 1 for name in fields}
            projection["_id"] = 0
            cursor = collection.find(filter_body, projection=projection)
            cursor = _apply_cursor_modifiers(cursor, stmt)
            rows = [
                Row(tuple(doc.get(f) for f in fields), tuple(fields))
                async for doc in cursor
            ]
            return AsyncSelectResult(rows)

        if isinstance(stmt, Insert):
            if not stmt._values:
                return Result(rowcount=0, inserted_ids=[])
            if len(stmt._values) == 1:
                r = await collection.insert_one(stmt._values[0])
                return Result(rowcount=1, inserted_ids=[str(r.inserted_id)])
            r = await collection.insert_many(stmt._values, ordered=True)
            return Result(
                rowcount=len(r.inserted_ids),
                inserted_ids=[str(_id) for _id in r.inserted_ids],
            )

        filter_body = ModelFieldOperation.to_mongo_filter(filters=stmt._filters)

        if isinstance(stmt, Update):
            r = await collection.update_many(filter_body, {"$set": stmt._values})
            return Result(rowcount=r.modified_count)

        if isinstance(stmt, Delete):
            r = await collection.delete_many(filter_body)
            return Result(rowcount=r.deleted_count)

        raise TypeError(
            f"execute() expects Insert, Update, Delete, or projection Select; "
            f"got {type(stmt).__name__}"
        )

    async def get(self, model: Type[_T], id: str) -> Optional[_T]:
        from mongotic.query import _hydrate_doc

        collection = self.engine[model.__databasename__][model.__tablename__]
        doc = await collection.find_one({"_id": ObjectId(id)})
        if doc is None:
            return None
        return _hydrate_doc(model, doc, self)  # type: ignore[return-value]

    # ── staging (sync) ────────────────────────────────────────────────────────

    def add(self, instance: MongoBaseModel) -> None:
        _assert_model_bound(instance)
        self._add_instances.append(instance)

    def add_all(self, instances: Sequence[MongoBaseModel]) -> None:
        for instance in instances:
            self.add(instance)

    def delete(self, instance: MongoBaseModel) -> None:
        _assert_model_bound(instance)
        self._delete_instances.append(instance)

    def _drop_pending_updates(self, instance: MongoBaseModel) -> None:
        keys = [k for k in self._update_instances if k[0] == id(instance)]
        for k in keys:
            del self._update_instances[k]

    def expunge(self, instance: MongoBaseModel) -> None:
        """Remove *instance* from all staging lists and detach it from the session."""
        self._add_instances = [x for x in self._add_instances if x is not instance]
        self._delete_instances = [
            x for x in self._delete_instances if x is not instance
        ]
        self._merge_instances = [x for x in self._merge_instances if x is not instance]
        self._drop_pending_updates(instance)
        object.__setattr__(instance, "_session", None)

    def expire(self, instance: MongoBaseModel) -> None:
        """Mark *instance* as expired and clear any pending field-level updates."""
        self._drop_pending_updates(instance)
        object.__setattr__(instance, "_expired", True)

    def merge(self, instance: MongoBaseModel) -> MongoBaseModel:
        """Stage *instance* for an upsert on the next flush/commit."""
        _assert_model_bound(instance)
        if instance._id is None:
            self._add_instances.append(instance)
        else:
            self._drop_pending_updates(instance)
            self._merge_instances.append(instance)
        object.__setattr__(instance, "_session", self)
        return instance

    # ── async I/O ops ─────────────────────────────────────────────────────────

    async def refresh(self, instance: MongoBaseModel) -> None:
        """Reload all fields of *instance* from the database in-place."""
        if instance._id is None:
            raise ValueError(
                "Cannot refresh an instance that has not been persisted (_id is None)"
            )
        collection = self.engine[instance.__databasename__][instance.__tablename__]
        doc = await collection.find_one({"_id": ObjectId(instance._id)})
        if doc is None:
            raise NotFound(
                f"Document with _id={instance._id!r} no longer exists in the database"
            )
        refreshed = instance.__class__(**doc)
        for field_name in instance.__class__.model_fields:
            object.__setattr__(instance, field_name, getattr(refreshed, field_name))
        self._drop_pending_updates(instance)
        object.__setattr__(instance, "_expired", False)

    # ── write control ─────────────────────────────────────────────────────────

    async def flush(self) -> None:
        """Write all staged ops to MongoDB immediately."""
        await self._execute_staged()

    async def commit(self) -> None:
        """Alias for flush(). Kept for SA v2 API familiarity."""
        await self._execute_staged()

    def rollback(self) -> None:
        """Discard staged (not yet flushed) changes."""
        self._clear_staging()

    async def close(self) -> None:
        """Discard any un-flushed staged changes."""
        self._clear_staging()

    # ── async context manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    # ── internals ─────────────────────────────────────────────────────────────

    async def _execute_staged(self) -> None:
        engine = self.engine

        for _add_instance in self._add_instances:
            _col = engine[_add_instance.__databasename__][_add_instance.__tablename__]
            result = await _col.insert_one(_add_instance.model_dump())
            object.__setattr__(_add_instance, "_id", str(result.inserted_id))
            object.__setattr__(_add_instance, "_session", self)

        for _update_instance in self._update_instances.values():
            _instance, _field_to_update, _new_value = _update_instance
            _col = engine[_instance.__databasename__][_instance.__tablename__]
            await _col.update_one(
                {"_id": ObjectId(_instance._id)},
                {"$set": {_field_to_update: _new_value}},
            )

        for _delete_instance in self._delete_instances:
            _col = engine[_delete_instance.__databasename__][
                _delete_instance.__tablename__
            ]
            await _col.delete_one({"_id": ObjectId(_delete_instance._id)})

        for _merge_instance in self._merge_instances:
            _col = engine[_merge_instance.__databasename__][
                _merge_instance.__tablename__
            ]
            await _col.replace_one(
                {"_id": ObjectId(_merge_instance._id)},
                _merge_instance.model_dump(),
                upsert=True,
            )
            object.__setattr__(_merge_instance, "_session", self)

        self._clear_staging()

    def _clear_staging(self) -> None:
        self._add_instances = []
        self._update_instances = {}
        self._delete_instances = []
        self._merge_instances = []


def async_sessionmaker(bind: AsyncMongoClient) -> Callable[[], AsyncSession]:
    """Factory that returns a callable producing AsyncSession instances bound to *bind*."""

    def _factory() -> AsyncSession:
        return AsyncSession(bind=bind)

    return _factory
