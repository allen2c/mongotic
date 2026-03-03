from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Text, Type

from pydantic import BaseModel, PrivateAttr
from pydantic._internal import _model_construction

if TYPE_CHECKING:
    from mongotic.orm import Session

NOT_SET_SENTINEL = object()


class Operator(Enum):
    EQUAL = auto()
    NOT_EQUAL = auto()
    GREATER_THAN = auto()
    GREATER_THAN_EQUAL = auto()
    LESS_THAN = auto()
    LESS_THAN_EQUAL = auto()
    IN = auto()
    NOT_IN = auto()

    def __str__(self):
        if self == Operator.EQUAL:
            return "=="
        elif self == Operator.NOT_EQUAL:
            return "!="
        elif self == Operator.GREATER_THAN:
            return ">"
        elif self == Operator.GREATER_THAN_EQUAL:
            return ">="
        elif self == Operator.LESS_THAN:
            return "<"
        elif self == Operator.LESS_THAN_EQUAL:
            return "<="
        elif self == Operator.IN:
            return "in"
        elif self == Operator.NOT_IN:
            return "not in"
        else:
            raise NotImplementedError


class SortDirection(Enum):
    ASC = 1
    DESC = -1


class ModelFieldSort(object):
    def __init__(self, model_field: "ModelField", direction: SortDirection):
        self.model_field = model_field
        self.direction = direction

    def __repr__(self) -> Text:
        return (
            f"<ModelFieldSort(FieldName={self.model_field.field_name}, "
            f"Direction={self.direction.name})>"
        )


class ModelFieldOperation(object):
    def __init__(self, model_field: "ModelField", operation: Operator, value: Any):
        self.model_field = model_field
        self.operation = operation
        self.value = value

    def __repr__(self) -> Text:
        return (
            "<ModelFieldOperation("
            + f"{self.model_field.field_name} {self.operation} {self.value}"
            ")>"
        )

    @classmethod
    def to_mongo_filter(
        cls, filters: List["ModelFieldOperation"], **kwargs
    ) -> Dict[Text, Any]:
        filter_dict: Dict[Text, Any] = {}

        for _filter in filters:
            if _filter.model_field.field_name not in filter_dict:
                filter_dict[_filter.model_field.field_name] = {}

            field_filter: Dict = filter_dict[_filter.model_field.field_name]

            if _filter.operation == Operator.EQUAL:
                field_filter.update({"$eq": _filter.value})
            elif _filter.operation == Operator.NOT_EQUAL:
                field_filter.update({"$ne": _filter.value})
            elif _filter.operation == Operator.GREATER_THAN:
                field_filter.update({"$gt": _filter.value})
            elif _filter.operation == Operator.GREATER_THAN_EQUAL:
                field_filter.update({"$gte": _filter.value})
            elif _filter.operation == Operator.LESS_THAN:
                field_filter.update({"$lt": _filter.value})
            elif _filter.operation == Operator.LESS_THAN_EQUAL:
                field_filter.update({"$lte": _filter.value})
            elif _filter.operation == Operator.IN:
                field_filter.update({"$in": _filter.value})
            elif _filter.operation == Operator.NOT_IN:
                field_filter.update({"$nin": _filter.value})
            else:
                raise NotImplementedError

        return filter_dict


class ModelField(object):
    def __init__(self, field_name: Text, model_class: Type["MongoBaseModel"]):
        self.field_name = field_name
        self.model_class = model_class

    def __repr__(self) -> Text:
        return f"<ModelField(FieldName={self.field_name}, Bind={self.model_class.__name__})>"

    def __eq__(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.EQUAL, value=other
        )

    def __ne__(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.NOT_EQUAL, value=other
        )

    def __gt__(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.GREATER_THAN, value=other
        )

    def __ge__(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.GREATER_THAN_EQUAL, value=other
        )

    def __lt__(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.LESS_THAN, value=other
        )

    def __le__(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.LESS_THAN_EQUAL, value=other
        )

    def in_(self, other: Any):
        return ModelFieldOperation(model_field=self, operation=Operator.IN, value=other)

    def not_in(self, other: Any):
        return ModelFieldOperation(
            model_field=self, operation=Operator.NOT_IN, value=other
        )

    def __neg__(self) -> "ModelFieldSort":
        return ModelFieldSort(model_field=self, direction=SortDirection.DESC)


class MongoBaseModelMeta(_model_construction.ModelMetaclass):
    def __getattr__(cls, item: Text):
        try:
            return super().__getattr__(item)
        except AttributeError as e:
            if item in cls.__dict__.get("__annotations__", {}):
                return ModelField(field_name=item, model_class=cls)
            else:
                raise e


class MongoBaseModel(BaseModel, metaclass=MongoBaseModelMeta):
    __databasename__: Text = NOT_SET_SENTINEL
    __tablename__: Text = NOT_SET_SENTINEL

    _id: Optional[Text] = PrivateAttr(None)
    _session: Optional["Session"] = PrivateAttr(None)

    def __setattr__(self, name: Text, value: Any) -> None:
        super().__setattr__(name, value)
        if self._session is not None and name not in ["_id", "_session"]:
            self._session._update_instances[(id(self), name)] = (self, name, value)
