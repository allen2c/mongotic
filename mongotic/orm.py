from __future__ import annotations

import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    Text,
    Tuple,
    Type,
    TypeVar,
)

if TYPE_CHECKING:
    from mongotic.query import Select

from bson.objectid import ObjectId
from pymongo import MongoClient

from mongotic.exceptions import MultipleResultsFound, NotFound
from mongotic.model import (
    ModelFieldOperation,
    MongoBaseModel,
    _assert_model_bound,
)
from mongotic.result import Result

_T = TypeVar("_T", bound=MongoBaseModel)


class ScalarResult(Generic[_T]):
    def __init__(
        self,
        collection: Any,
        stmt: Any,
        model: Type[_T],
        session: Any,
    ):
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

    def all(self) -> List[Any]:
        if self._stmt._distinct_field is not None:
            return self._collection.distinct(
                self._stmt._distinct_field.field_name, self._compiled_filter
            )
        return [self._extract_value(doc) for doc in self._build_cursor()]

    def first(self) -> Optional[_T]:
        for doc in self._build_cursor().limit(1):
            return self._extract_value(doc)
        return None

    def one(self) -> _T:
        docs = list(self._build_cursor().limit(2))
        if len(docs) == 0:
            raise NotFound("No result found")
        if len(docs) > 1:
            raise MultipleResultsFound("Expected one result, got multiple")
        return self._extract_value(docs[0])

    def one_or_none(self) -> Optional[_T]:
        docs = list(self._build_cursor().limit(2))
        if len(docs) == 0:
            return None
        if len(docs) > 1:
            raise MultipleResultsFound("Expected one result, got multiple")
        return self._extract_value(docs[0])

    def count(self) -> int:
        return self._collection.count_documents(self._compiled_filter)

    def exists(self) -> bool:
        return self._collection.count_documents(self._compiled_filter, limit=1) > 0

    def __iter__(self) -> Iterator[_T]:
        for doc in self._build_cursor():
            yield self._extract_value(doc)


class Session(Protocol):
    engine: MongoClient
    _add_instances: List[MongoBaseModel]
    _update_instances: Dict[Tuple[int, Text], Tuple[MongoBaseModel, Text, Any]]
    _delete_instances: List[MongoBaseModel]
    _merge_instances: List[MongoBaseModel]

    def __init__(self, **kwargs: Any): ...

    @property
    def new(self) -> List[MongoBaseModel]: ...

    @property
    def dirty(self) -> List[MongoBaseModel]: ...

    @property
    def deleted(self) -> List[MongoBaseModel]: ...

    def scalars(self, stmt: Select[_T]) -> ScalarResult[_T]: ...

    def scalar(self, stmt: Any) -> Any: ...

    def execute(self, stmt: Any) -> Result: ...

    def get(self, model: Type[_T], id: Text) -> Optional[_T]: ...

    def add(self, instance: MongoBaseModel) -> None: ...

    def add_all(self, instances: List[MongoBaseModel]) -> None: ...

    def delete(self, instance: MongoBaseModel) -> None: ...

    def expunge(self, instance: MongoBaseModel) -> None: ...

    def expire(self, instance: MongoBaseModel) -> None: ...

    def refresh(self, instance: MongoBaseModel) -> None: ...

    def merge(self, instance: MongoBaseModel) -> MongoBaseModel: ...

    def flush(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> Session: ...

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None: ...


def sessionmaker(bind: MongoClient) -> Type[Session]:
    class _Session:
        def __init__(self):
            self.engine = bind
            self._add_instances: List[MongoBaseModel] = []
            self._update_instances: Dict[
                Tuple[int, Text], Tuple[MongoBaseModel, Text, Any]
            ] = {}
            self._delete_instances: List[MongoBaseModel] = []
            self._merge_instances: List[MongoBaseModel] = []

        # ── state properties ─────────────────────────────────────────────────

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

        # ── querying ────────────────────────────────────────────────────────

        def scalars(self, stmt: Select[_T]) -> ScalarResult[_T]:
            from mongotic.query import Select

            if not isinstance(stmt, Select):
                raise TypeError(
                    f"scalars() expects a Select statement, got {type(stmt)}"
                )
            if stmt.is_projection and stmt.projection_field_count > 1:
                raise TypeError(
                    "session.scalars() requires a single-column select; got multiple columns"
                )
            collection = self.engine[stmt._model.__databasename__][
                stmt._model.__tablename__
            ]
            return ScalarResult(
                collection=collection,
                stmt=stmt,
                model=stmt._model,
                session=self,
            )

        def scalar(self, stmt: Any) -> Any:
            return self.scalars(stmt).first()

        def execute(self, stmt: Any) -> Result:
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
                from mongotic.result import Row, SelectResult

                fields = stmt.projection_field_names
                filter_body = ModelFieldOperation.to_mongo_filter(filters=stmt._filters)
                projection = {name: 1 for name in fields}
                projection["_id"] = 0
                cursor = collection.find(filter_body, projection=projection)
                cursor = _apply_cursor_modifiers(cursor, stmt)
                rows = [
                    Row(tuple(doc.get(f) for f in fields), tuple(fields))
                    for doc in cursor
                ]
                return SelectResult(rows)

            if isinstance(stmt, Insert):
                if not stmt._values:
                    return Result(rowcount=0, inserted_ids=[])
                if len(stmt._values) == 1:
                    r = collection.insert_one(stmt._values[0])
                    return Result(rowcount=1, inserted_ids=[str(r.inserted_id)])
                r = collection.insert_many(stmt._values, ordered=True)
                return Result(
                    rowcount=len(r.inserted_ids),
                    inserted_ids=[str(_id) for _id in r.inserted_ids],
                )

            filter_body = ModelFieldOperation.to_mongo_filter(filters=stmt._filters)

            if isinstance(stmt, Update):
                r = collection.update_many(filter_body, {"$set": stmt._values})
                return Result(rowcount=r.modified_count)

            if isinstance(stmt, Delete):
                r = collection.delete_many(filter_body)
                return Result(rowcount=r.deleted_count)

            raise TypeError(
                f"execute() expects Insert, Update, Delete, or projection Select, "
                f"got {type(stmt).__name__}"
            )

        def get(self, model: Type[_T], id: Text) -> Optional[_T]:
            from mongotic.query import _hydrate_doc

            collection = self.engine[model.__databasename__][model.__tablename__]
            doc = collection.find_one({"_id": ObjectId(id)})
            if doc is None:
                return None
            return _hydrate_doc(model, doc, self)  # type: ignore[return-value]

        # ── writing ─────────────────────────────────────────────────────────

        def add(self, instance: MongoBaseModel) -> None:
            _assert_model_bound(instance)
            self._add_instances.append(instance)

        def add_all(self, instances: List[MongoBaseModel]) -> None:
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
            """Remove *instance* from all staging lists and detach it from the session.

            After expunge the instance is untracked: mutations will not be staged
            and ``_session`` is cleared to ``None``.  Calling expunge on an instance
            that is not currently tracked is a safe no-op."""
            self._add_instances = [x for x in self._add_instances if x is not instance]
            self._delete_instances = [
                x for x in self._delete_instances if x is not instance
            ]
            self._merge_instances = [
                x for x in self._merge_instances if x is not instance
            ]
            self._drop_pending_updates(instance)
            object.__setattr__(instance, "_session", None)

        def expire(self, instance: MongoBaseModel) -> None:
            """Mark *instance* as expired and clear any pending field-level updates.

            The instance remains attached to the session.  Cached field values are
            still readable; the ``_expired`` flag is set to ``True`` to signal that
            the data may be stale.  Call ``session.refresh(instance)`` to reload
            from the database."""
            self._drop_pending_updates(instance)
            object.__setattr__(instance, "_expired", True)

        def refresh(self, instance: MongoBaseModel) -> None:
            """Reload all fields of *instance* from the database in-place.
            Clears any pending field-level updates for this instance.

            Note: if the instance is staged for deletion, the deletion staging
            is preserved — call ``session.rollback()`` first to cancel it."""
            if instance._id is None:
                raise ValueError(
                    "Cannot refresh an instance that has not been persisted (_id is None)"
                )
            collection = self.engine[instance.__databasename__][instance.__tablename__]
            doc = collection.find_one({"_id": ObjectId(instance._id)})
            if doc is None:
                raise NotFound(
                    f"Document with _id={instance._id!r} no longer exists in the database"
                )
            refreshed = instance.__class__(**doc)
            for field_name in instance.__class__.model_fields:
                object.__setattr__(instance, field_name, getattr(refreshed, field_name))
            # Clear any pending updates for this instance and reset expired flag
            self._drop_pending_updates(instance)
            object.__setattr__(instance, "_expired", False)

        def merge(self, instance: MongoBaseModel) -> MongoBaseModel:
            """Stage *instance* for an upsert on the next flush/commit.
            If *instance* has no _id, behaves like session.add().
            Returns the instance with _session bound."""
            _assert_model_bound(instance)
            if instance._id is None:
                self._add_instances.append(instance)
            else:
                # replace_one will write the full document; discard any pending
                # field-level updates for this instance to avoid redundant writes
                self._drop_pending_updates(instance)
                self._merge_instances.append(instance)
            instance._session = self
            return instance

        # ── write control (no transactions) ──────────────────────────────────

        def flush(self) -> None:
            """Write all staged ops to MongoDB immediately. Each write is document-atomic.
            After flush, changes are persisted and cannot be undone by rollback()."""
            self._execute_staged()

        def commit(self) -> None:
            """Alias for flush(). Kept for SA v2 API familiarity."""
            self._execute_staged()

        def rollback(self) -> None:
            """Discard staged (not yet flushed) changes.
            Cannot undo writes that have already been flushed."""
            self._clear_staging()

        def close(self) -> None:
            """Discard any un-flushed staged changes."""
            self._clear_staging()

        # ── context manager ──────────────────────────────────────────────────

        def __enter__(self) -> _Session:
            return self

        def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
            self.close()

        # ── internals ────────────────────────────────────────────────────────

        def _execute_staged(self) -> None:
            engine = self.engine

            for _add_instance in self._add_instances:
                _col = engine[_add_instance.__databasename__][
                    _add_instance.__tablename__
                ]
                result = _col.insert_one(_add_instance.model_dump())
                _add_instance._id = str(result.inserted_id)
                _add_instance._session = self

            for _update_instance in self._update_instances.values():
                _instance, _field_to_update, _new_value = _update_instance
                _col = engine[_instance.__databasename__][_instance.__tablename__]
                _col.update_one(
                    {"_id": ObjectId(_instance._id)},
                    {"$set": {_field_to_update: _new_value}},
                )

            for _delete_instance in self._delete_instances:
                _col = engine[_delete_instance.__databasename__][
                    _delete_instance.__tablename__
                ]
                _col.delete_one({"_id": ObjectId(_delete_instance._id)})

            for _merge_instance in self._merge_instances:
                _col = engine[_merge_instance.__databasename__][
                    _merge_instance.__tablename__
                ]
                _col.replace_one(
                    {"_id": ObjectId(_merge_instance._id)},
                    _merge_instance.model_dump(),
                    upsert=True,
                )
                _merge_instance._session = self

            self._clear_staging()

        def _clear_staging(self) -> None:
            self._add_instances = []
            self._update_instances = {}
            self._delete_instances = []
            self._merge_instances = []

    return _Session
