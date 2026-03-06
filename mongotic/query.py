from typing import Any, Dict, Generic, List, Optional, Text, Type, TypeVar, Union

from mongotic.model import (
    CompoundFilter,
    FilterType,
    ModelField,
    ModelFieldOperation,
    ModelFieldSort,
    MongoBaseModel,
    SortDirection,
)

_T = TypeVar("_T", bound="MongoBaseModel")


class Select(Generic[_T]):
    def __init__(self, orm_model: Type[_T]):
        self._model = orm_model
        self._filters: List["FilterType"] = []
        self._sort: List["ModelFieldSort"] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._distinct_field: Optional["ModelField"] = None

    def where(self, *conditions: "FilterType") -> "Select[_T]":
        self._filters.extend(conditions)
        return self

    def distinct(self, field: "ModelField") -> "Select[_T]":
        """Return unique values for *field* using MongoDB ``collection.distinct()``.

        Call ``.all()`` on the resulting ``ScalarResult`` to retrieve a
        ``List[Any]`` of distinct values.

        Note: ``.order_by()``, ``.limit()``, and ``.offset()`` are ignored for
        distinct queries — MongoDB's ``distinct`` command does not support them.
        """
        self._distinct_field = field
        return self

    def order_by(self, *fields: Union["ModelFieldSort", Any]) -> "Select[_T]":
        for field in fields:
            if isinstance(field, ModelFieldSort):
                self._sort.append(field)
            elif isinstance(field, ModelField):
                self._sort.append(
                    ModelFieldSort(model_field=field, direction=SortDirection.ASC)
                )
            else:
                raise TypeError(
                    f"order_by expects ModelField or -ModelField, got {type(field)}"
                )
        return self

    def limit(self, value: int) -> "Select[_T]":
        if value < 0:
            raise ValueError("Limit value must be non-negative")
        self._limit = value
        return self

    def offset(self, value: int) -> "Select[_T]":
        if value < 0:
            raise ValueError("Offset value must be non-negative")
        self._offset = value
        return self


class Update:
    def __init__(self, orm_model: Type["MongoBaseModel"]):
        self._model = orm_model
        self._filters: List["FilterType"] = []
        self._values: Dict[Text, Any] = {}

    def where(self, *conditions: "FilterType") -> "Update":
        self._filters.extend(conditions)
        return self

    def values(self, **kwargs: Any) -> "Update":
        self._values.update(kwargs)
        return self


class Delete:
    def __init__(self, orm_model: Type["MongoBaseModel"]):
        self._model = orm_model
        self._filters: List["FilterType"] = []

    def where(self, *conditions: "FilterType") -> "Delete":
        self._filters.extend(conditions)
        return self


def select(orm_model: Type[_T]) -> Select[_T]:
    return Select(orm_model=orm_model)


def update(orm_model: Type["MongoBaseModel"]) -> Update:
    return Update(orm_model=orm_model)


def delete(orm_model: Type["MongoBaseModel"]) -> Delete:
    return Delete(orm_model=orm_model)
