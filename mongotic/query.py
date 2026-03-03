from typing import Any, Dict, List, Optional, Text, Type, Union

from mongotic.model import (
    ModelFieldOperation,
    ModelFieldSort,
    MongoBaseModel,
    SortDirection,
)


class Select:
    def __init__(self, orm_model: Type["MongoBaseModel"]):
        self._model = orm_model
        self._filters: List["ModelFieldOperation"] = []
        self._sort: List["ModelFieldSort"] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def where(self, *model_field_operations: "ModelFieldOperation") -> "Select":
        self._filters.extend(model_field_operations)
        return self

    def order_by(self, *fields: Union["ModelFieldSort", Any]) -> "Select":
        from mongotic.model import ModelField

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

    def limit(self, value: int) -> "Select":
        if value < 0:
            raise ValueError("Limit value must be non-negative")
        self._limit = value
        return self

    def offset(self, value: int) -> "Select":
        if value < 0:
            raise ValueError("Offset value must be non-negative")
        self._offset = value
        return self


class Update:
    def __init__(self, orm_model: Type["MongoBaseModel"]):
        self._model = orm_model
        self._filters: List["ModelFieldOperation"] = []
        self._values: Dict[Text, Any] = {}

    def where(self, *model_field_operations: "ModelFieldOperation") -> "Update":
        self._filters.extend(model_field_operations)
        return self

    def values(self, **kwargs: Any) -> "Update":
        self._values.update(kwargs)
        return self


class Delete:
    def __init__(self, orm_model: Type["MongoBaseModel"]):
        self._model = orm_model
        self._filters: List["ModelFieldOperation"] = []

    def where(self, *model_field_operations: "ModelFieldOperation") -> "Delete":
        self._filters.extend(model_field_operations)
        return self


def select(orm_model: Type["MongoBaseModel"]) -> Select:
    return Select(orm_model=orm_model)


def update(orm_model: Type["MongoBaseModel"]) -> Update:
    return Update(orm_model=orm_model)


def delete(orm_model: Type["MongoBaseModel"]) -> Delete:
    return Delete(orm_model=orm_model)
