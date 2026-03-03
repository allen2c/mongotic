from typing import Any, List, Optional, Protocol, Text, Tuple, Type

from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.client_session import ClientSession
from typing_extensions import ParamSpec

from mongotic.exceptions import NotFound
from mongotic.model import (
    NOT_SET_SENTINEL,
    ModelField,
    ModelFieldOperation,
    MongoBaseModel,
)

P = ParamSpec("P")


class QuerySet:
    def __init__(
        self,
        orm_model: Type["MongoBaseModel"],
        *args: Any,
        engine: "MongoClient",
        session: "Session",
        **kwargs: Any
    ):
        self.orm_model = orm_model
        self.engine = engine
        self.session = session

        if self.orm_model.__databasename__ is NOT_SET_SENTINEL:
            raise ValueError("Database name is not set")
        if self.orm_model.__tablename__ is NOT_SET_SENTINEL:
            raise ValueError("Table name is not set")

        self._db_name: Text = self.orm_model.__databasename__
        self._col_name: Text = self.orm_model.__tablename__
        self._limit = 5
        self._offset = 0
        self._filters: List["ModelFieldOperation"] = []

    def filter(
        self, *model_field_operations: "ModelFieldOperation", **kwargs: Any
    ) -> "QuerySet":
        if not model_field_operations and not kwargs:
            raise ValueError("No filter is provided")

        self._filters.extend(model_field_operations)

        for k, v in kwargs.items():
            self._filters.append(
                ModelField(field_name=k, model_class=self.orm_model) == v
            )

        return self

    def filter_by(self, **kwargs: Any) -> "QuerySet":
        for k, v in kwargs.items():
            self._filters.append(
                ModelField(field_name=k, model_class=self.orm_model) == v
            )
        return self

    def limit(self, value: int, *args: Any, **kwargs: Any) -> "QuerySet":
        if value < 0:
            raise ValueError("Limit value must be positive")
        self._limit = value
        return self

    def offset(self, value: int, *args: Any, **kwargs: Any) -> "QuerySet":
        if value < 0:
            raise ValueError("Offset value must be positive")
        self._offset = value
        return self

    def first(self, *args: Any, **kwargs: Any) -> "MongoBaseModel":
        collection = self.engine[self._db_name][self._col_name]

        filter_body = ModelFieldOperation.to_mongo_filter(filters=self._filters)
        doc_raw = collection.find_one(filter=filter_body)
        if not doc_raw:
            raise NotFound

        doc = self.orm_model(**doc_raw)
        doc._id = str(doc_raw["_id"])
        doc._session = self.session
        return doc

    def all(self, *args: Any, **kwargs: Any) -> List["MongoBaseModel"]:
        docs: List["MongoBaseModel"] = []

        collection = self.engine[self._db_name][self._col_name]

        filter_body = ModelFieldOperation.to_mongo_filter(filters=self._filters)

        for _doc in collection.find(filter_body).skip(self._offset).limit(self._limit):
            _doc_orm = self.orm_model(**_doc)
            _doc_orm._id = str(_doc["_id"])
            _doc_orm._session = self.session
            docs.append(_doc_orm)

        return docs


class Session(Protocol):
    engine: "MongoClient"
    client_session: Optional["ClientSession"]
    _add_instances: List["MongoBaseModel"]
    _update_instances: List[Tuple["MongoBaseModel", Text, Any]]

    def __init__(self, bind_engine: MongoClient, **kwargs: Any): ...

    def query(
        self, orm_model: Type["MongoBaseModel"], *args: Any, **kwargs: Any
    ) -> QuerySet: ...

    def add(self, instance: "MongoBaseModel", *args: Any, **kwargs: Any) -> None: ...

    def delete(self, instance: "MongoBaseModel", *args: Any, **kwargs: Any) -> None: ...

    def commit(self, *args: Any, **kwargs: Any) -> None: ...

    def __enter__(self): ...

    def __exit__(self, exc_type, exc_value, traceback): ...


def sessionmaker(bind: "MongoClient") -> Type[Session]:
    class _Session:
        def __init__(self, *args, **kwargs: Any):
            self.engine = bind

            self.client_session: Optional["ClientSession"] = None

            self._add_instances: List["MongoBaseModel"] = []
            self._update_instances: List[Tuple["MongoBaseModel", Text, Any]] = []
            self._delete_instances: List["MongoBaseModel"] = []

        def query(
            self, orm_model: Type["MongoBaseModel"], *args: Any, **kwargs: Any
        ) -> QuerySet:
            return QuerySet(
                orm_model=orm_model, *args, engine=self.engine, session=self, **kwargs
            )

        def add(self, instance: "MongoBaseModel", *args: Any, **kwargs: Any) -> None:
            if instance.__databasename__ is NOT_SET_SENTINEL:
                raise ValueError("Database name is not set")
            if instance.__tablename__ is NOT_SET_SENTINEL:
                raise ValueError("Table name is not set")

            self._add_instances.append(instance)

        def delete(self, instance: "MongoBaseModel", *args: Any, **kwargs: Any) -> None:
            if instance.__databasename__ is NOT_SET_SENTINEL:
                raise ValueError("Database name is not set")
            if instance.__tablename__ is NOT_SET_SENTINEL:
                raise ValueError("Table name is not set")

            self._delete_instances.append(instance)

        def commit(self, *args: Any, **kwargs: Any) -> None:
            if self.client_session is None:
                with self:
                    assert (
                        self.client_session is not None
                    ), "Client session should be created in Session.__enter__"
                    with self.client_session.start_transaction():
                        self._commit(
                            pymongo_client_session=self.client_session,
                            engine=self.engine,
                            add_instances=self._add_instances,
                            update_instances=self._update_instances,
                        )

            else:
                with self.client_session.start_transaction():
                    self._commit(
                        pymongo_client_session=self.client_session,
                        engine=self.engine,
                        add_instances=self._add_instances,
                        update_instances=self._update_instances,
                    )

            self._add_instances = []
            self._update_instances = []
            self._delete_instances = []

        def __enter__(self):
            self.client_session = self.engine.start_session()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.client_session.end_session()
            self.client_session = None

        def _commit(
            self,
            pymongo_client_session: "ClientSession",
            engine: "MongoClient",
            add_instances: List["MongoBaseModel"],
            update_instances: List[Tuple["MongoBaseModel", Text, Any]],
        ) -> None:
            for _add_instance in add_instances:
                _db = engine[_add_instance.__databasename__]
                _col = _db[_add_instance.__tablename__]
                _insert_one_result = _col.insert_one(
                    _add_instance.model_dump(), session=pymongo_client_session
                )
                _add_instance._id = str(_insert_one_result.inserted_id)
                _add_instance._session = self

            for _update_instance in self._update_instances:
                _instance, _field_to_update, _new_value = _update_instance
                _db = engine[_instance.__databasename__]
                _col = _db[_instance.__tablename__]
                _col.update_one(
                    {"_id": _instance._id}, {"$set": {_field_to_update: _new_value}}
                )

            for _delete_instance in self._delete_instances:
                _db = engine[_delete_instance.__databasename__]
                _col = _db[_delete_instance.__tablename__]
                _col.delete_one({"_id": ObjectId(_delete_instance._id)})

    return _Session
