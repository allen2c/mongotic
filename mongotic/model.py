import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Text, Type, Union

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
    BETWEEN = auto()
    REGEX = auto()

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
        elif self == Operator.BETWEEN:
            return "between"
        elif self == Operator.REGEX:
            return "regex"
        else:
            raise NotImplementedError


@dataclass
class RegexValue:
    """Holds a MongoDB ``$regex`` pattern and optional flags."""

    pattern: Text
    options: Text = ""


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

    @staticmethod
    def to_mongo_filter(
        filters: "List[Union[ModelFieldOperation, CompoundFilter]]",
    ) -> Dict[Text, Any]:
        filter_dict: Dict[Text, Any] = {}

        for _filter in filters:
            if isinstance(_filter, CompoundFilter):
                cf_dict = _filter.to_mongo_filter()
                for key, val in cf_dict.items():
                    if (
                        key in filter_dict
                        and isinstance(filter_dict[key], dict)
                        and isinstance(val, dict)
                    ):
                        filter_dict[key].update(val)
                    else:
                        filter_dict[key] = val
                continue

            if _filter.model_field.field_name not in filter_dict:
                filter_dict[_filter.model_field.field_name] = {}

            field_filter: Dict = filter_dict[_filter.model_field.field_name]

            field_filter.update(_op_to_expr(_filter))

        return filter_dict


_OP_MAP: Dict[Operator, Text] = {
    Operator.EQUAL: "$eq",
    Operator.NOT_EQUAL: "$ne",
    Operator.GREATER_THAN: "$gt",
    Operator.GREATER_THAN_EQUAL: "$gte",
    Operator.LESS_THAN: "$lt",
    Operator.LESS_THAN_EQUAL: "$lte",
    Operator.IN: "$in",
    Operator.NOT_IN: "$nin",
}


def _op_to_expr(op: "ModelFieldOperation") -> Dict[Text, Any]:
    """Return the MongoDB operator expression for one op (without the field name)."""
    if op.operation in _OP_MAP:
        return {_OP_MAP[op.operation]: op.value}
    if op.operation == Operator.BETWEEN:
        low, high = op.value
        return {"$gte": low, "$lte": high}
    if op.operation == Operator.REGEX:
        expr: Dict[Text, Any] = {"$regex": op.value.pattern}
        if op.value.options:
            expr["$options"] = op.value.options
        return expr
    raise NotImplementedError(f"No MongoDB expression for operator {op.operation}")


def _single_op_to_filter(op: "ModelFieldOperation") -> Dict[Text, Any]:
    """Convert a single ModelFieldOperation to ``{field: {mongo_op: value}}``."""
    return {op.model_field.field_name: _op_to_expr(op)}


class CompoundFilter:
    """Represents logical compound filters: $or, $and, $nor, or field-level $not."""

    def __init__(
        self,
        op: Text,
        children: "List[Union[ModelFieldOperation, CompoundFilter]]",
    ):
        self.op = op
        self._children = children

    def __repr__(self) -> Text:
        return f"<CompoundFilter(op={self.op}, n_children={len(self._children)})>"

    def to_mongo_filter(self) -> Dict[Text, Any]:
        # Special case: field-level $not wrapping a single ModelFieldOperation
        if self.op == "$not_field":
            child = self._children[0]
            assert isinstance(child, ModelFieldOperation)
            return {child.model_field.field_name: {"$not": _op_to_expr(child)}}

        child_filters: List[Dict[Text, Any]] = []
        for child in self._children:
            if isinstance(child, ModelFieldOperation):
                child_filters.append(_single_op_to_filter(child))
            else:
                child_filters.append(child.to_mongo_filter())
        return {self.op: child_filters}


# Type alias for anything accepted in .where() / to_mongo_filter()
FilterType = Union[ModelFieldOperation, CompoundFilter]


def or_(*conditions: FilterType) -> CompoundFilter:
    """Combine conditions with logical OR ($or)."""
    return CompoundFilter(op="$or", children=list(conditions))


def and_(*conditions: FilterType) -> CompoundFilter:
    """Combine conditions with logical AND ($and)."""
    return CompoundFilter(op="$and", children=list(conditions))


def not_(condition: FilterType) -> CompoundFilter:
    """Negate a condition.

    - Single ModelFieldOperation  → field-level ``$not``
    - CompoundFilter (or_)        → ``$nor`` with flattened children
    - CompoundFilter (other)      → ``$nor`` wrapping the compound filter
    """
    if isinstance(condition, ModelFieldOperation):
        return CompoundFilter(op="$not_field", children=[condition])
    if isinstance(condition, CompoundFilter):
        if condition.op == "$or":
            # not_(or_(A, B)) == $nor: [A, B]
            return CompoundFilter(op="$nor", children=condition._children)
        # not_(and_(...)) or other nesting: wrap in single-element $nor
        return CompoundFilter(op="$nor", children=[condition])
    raise TypeError(
        f"not_() expects ModelFieldOperation or CompoundFilter, got {type(condition)}"
    )


def _like_to_regex(pattern: Text) -> Text:
    """Convert a SQL LIKE pattern to an anchored regex string.

    ``%`` → ``.*``, ``_`` → ``.``, all other chars are ``re.escape``-d.
    """
    parts: List[Text] = []
    for ch in pattern:
        if ch == "%":
            parts.append(".*")
        elif ch == "_":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    return "^" + "".join(parts) + "$"


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

    def is_(self, value: Any) -> "ModelFieldOperation":
        """Match documents where the field equals *value* (supports ``None`` for null check)."""
        return ModelFieldOperation(
            model_field=self, operation=Operator.EQUAL, value=value
        )

    def is_not(self, value: Any) -> "ModelFieldOperation":
        """Match documents where the field does not equal *value* (supports ``None``)."""
        return ModelFieldOperation(
            model_field=self, operation=Operator.NOT_EQUAL, value=value
        )

    # ── string operators ────────────────────────────────────────────────────

    def like(self, pattern: Text) -> "ModelFieldOperation":
        """SQL LIKE match (``%`` = any chars, ``_`` = one char). Case-sensitive."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=_like_to_regex(pattern)),
        )

    def ilike(self, pattern: Text) -> "ModelFieldOperation":
        """Case-insensitive SQL LIKE match."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=_like_to_regex(pattern), options="i"),
        )

    def contains(self, value: Text) -> "ModelFieldOperation":
        """Substring match (case-sensitive)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=re.escape(value)),
        )

    def startswith(self, value: Text) -> "ModelFieldOperation":
        """Prefix match (case-sensitive)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern="^" + re.escape(value)),
        )

    def endswith(self, value: Text) -> "ModelFieldOperation":
        """Suffix match (case-sensitive)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=re.escape(value) + "$"),
        )

    # ── range operator ───────────────────────────────────────────────────────

    def between(self, low: Any, high: Any) -> "ModelFieldOperation":
        """Inclusive range: ``low <= field <= high``.

        Equivalent to ``and_(field >= low, field <= high)`` but rendered as a
        single ``{"$gte": low, "$lte": high}`` expression for index efficiency.
        """
        return ModelFieldOperation(
            model_field=self, operation=Operator.BETWEEN, value=(low, high)
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
