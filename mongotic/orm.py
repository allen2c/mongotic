from typing import Any, Dict, List, Optional, Protocol, Text, Tuple, Type

from bson.objectid import ObjectId
from pymongo import MongoClient

from mongotic.exceptions import MultipleResultsFound, NotFound
from mongotic.model import (
    NOT_SET_SENTINEL,
    MongoBaseModel,
)


class ScalarResult:
    def __init__(
        self,
        collection: Any,
        stmt: Any,
        model: Type["MongoBaseModel"],
        session: Any,
    ):
        self._collection = collection
        self._stmt = stmt
        self._model = model
        self._session = session

    def _build_cursor(self):
        from pymongo import ASCENDING, DESCENDING

        from mongotic.model import ModelFieldOperation, SortDirection

        filter_body = ModelFieldOperation.to_mongo_filter(filters=self._stmt._filters)
        cursor = self._collection.find(filter_body)

        if self._stmt._sort:
            sort_list = [
                (
                    s.model_field.field_name,
                    ASCENDING if s.direction == SortDirection.ASC else DESCENDING,
                )
                for s in self._stmt._sort
            ]
            cursor = cursor.sort(sort_list)

        if self._stmt._offset is not None:
            cursor = cursor.skip(self._stmt._offset)
        if self._stmt._limit is not None:
            cursor = cursor.limit(self._stmt._limit)

        return cursor

    def _hydrate(self, doc_raw: Dict) -> "MongoBaseModel":
        obj = self._model(**doc_raw)
        obj._id = str(doc_raw["_id"])
        obj._session = self._session
        return obj

    def all(self) -> List["MongoBaseModel"]:
        return [self._hydrate(doc) for doc in self._build_cursor()]

    def first(self) -> Optional["MongoBaseModel"]:
        from mongotic.model import ModelFieldOperation

        filter_body = ModelFieldOperation.to_mongo_filter(filters=self._stmt._filters)
        doc = self._collection.find_one(filter_body)
        return self._hydrate(doc) if doc else None

    def one(self) -> "MongoBaseModel":
        results = self.all()
        if len(results) == 0:
            raise NotFound("No result found")
        if len(results) > 1:
            raise MultipleResultsFound(f"Expected one result, got {len(results)}")
        return results[0]

    def one_or_none(self) -> Optional["MongoBaseModel"]:
        results = self.all()
        if len(results) == 0:
            return None
        if len(results) > 1:
            raise MultipleResultsFound(f"Expected one result, got {len(results)}")
        return results[0]

    def count(self) -> int:
        from mongotic.model import ModelFieldOperation

        filter_body = ModelFieldOperation.to_mongo_filter(filters=self._stmt._filters)
        return self._collection.count_documents(filter_body)

    def exists(self) -> bool:
        from mongotic.model import ModelFieldOperation

        filter_body = ModelFieldOperation.to_mongo_filter(filters=self._stmt._filters)
        return self._collection.count_documents(filter_body, limit=1) > 0


class Session(Protocol):
    engine: "MongoClient"
    _add_instances: List["MongoBaseModel"]
    _update_instances: Dict[Tuple[int, Text], Tuple["MongoBaseModel", Text, Any]]
    _delete_instances: List["MongoBaseModel"]

    def __init__(self, **kwargs: Any): ...

    def scalars(self, stmt: Any) -> "ScalarResult": ...

    def execute(self, stmt: Any) -> int: ...

    def get(
        self, model: Type["MongoBaseModel"], id: Text
    ) -> Optional["MongoBaseModel"]: ...

    def add(self, instance: "MongoBaseModel") -> None: ...

    def add_all(self, instances: List["MongoBaseModel"]) -> None: ...

    def delete(self, instance: "MongoBaseModel") -> None: ...

    def flush(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> "Session": ...

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None: ...


def sessionmaker(bind: "MongoClient") -> Type[Session]:
    class _Session:
        def __init__(self, *args: Any, **kwargs: Any):
            self.engine = bind
            self._add_instances: List["MongoBaseModel"] = []
            self._update_instances: Dict[
                Tuple[int, Text], Tuple["MongoBaseModel", Text, Any]
            ] = {}
            self._delete_instances: List["MongoBaseModel"] = []

        # ── querying ────────────────────────────────────────────────────────

        def scalars(self, stmt: Any) -> "ScalarResult":
            from mongotic.query import Select

            if not isinstance(stmt, Select):
                raise TypeError(
                    f"scalars() expects a Select statement, got {type(stmt)}"
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

        def execute(self, stmt: Any) -> int:
            from mongotic.model import ModelFieldOperation
            from mongotic.query import Delete, Update

            filter_body = ModelFieldOperation.to_mongo_filter(filters=stmt._filters)
            collection = self.engine[stmt._model.__databasename__][
                stmt._model.__tablename__
            ]
            if isinstance(stmt, Update):
                result = collection.update_many(filter_body, {"$set": stmt._values})
                return result.modified_count
            elif isinstance(stmt, Delete):
                result = collection.delete_many(filter_body)
                return result.deleted_count
            else:
                raise TypeError(f"execute() expects Update or Delete, got {type(stmt)}")

        def get(
            self, model: Type["MongoBaseModel"], id: Text
        ) -> Optional["MongoBaseModel"]:
            collection = self.engine[model.__databasename__][model.__tablename__]
            doc = collection.find_one({"_id": ObjectId(id)})
            if doc is None:
                return None
            obj = model(**doc)
            obj._id = str(doc["_id"])
            obj._session = self
            return obj

        # ── writing ─────────────────────────────────────────────────────────

        def add(self, instance: "MongoBaseModel") -> None:
            if instance.__databasename__ is NOT_SET_SENTINEL:
                raise ValueError("Database name is not set")
            if instance.__tablename__ is NOT_SET_SENTINEL:
                raise ValueError("Table name is not set")
            self._add_instances.append(instance)

        def add_all(self, instances: List["MongoBaseModel"]) -> None:
            for instance in instances:
                self.add(instance)

        def delete(self, instance: "MongoBaseModel") -> None:
            if instance.__databasename__ is NOT_SET_SENTINEL:
                raise ValueError("Database name is not set")
            if instance.__tablename__ is NOT_SET_SENTINEL:
                raise ValueError("Table name is not set")
            self._delete_instances.append(instance)

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

        def __enter__(self) -> "_Session":
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

            self._clear_staging()

        def _clear_staging(self) -> None:
            self._add_instances = []
            self._update_instances = {}
            self._delete_instances = []

    return _Session
