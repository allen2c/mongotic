import re
import warnings
from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    TypeVar,
    Union,
    get_args,
    overload,
)

from pydantic import BaseModel, GetCoreSchemaHandler, PrivateAttr
from pydantic._internal import _model_construction
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, core_schema

if TYPE_CHECKING:
    from mongotic.orm import Session

NOT_SET_SENTINEL = object()

_T_field = TypeVar("_T_field")


def _assert_model_bound(instance):
    if instance.__databasename__ is NOT_SET_SENTINEL:
        raise ValueError("Database name is not set")
    if instance.__tablename__ is NOT_SET_SENTINEL:
        raise ValueError("Table name is not set")


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

    pattern: str
    options: str = ""


class SortDirection(Enum):
    ASC = 1
    DESC = -1


class ModelFieldSort(object):
    def __init__(self, model_field: "ModelField", direction: SortDirection):
        self.model_field = model_field
        self.direction = direction

    def __repr__(self) -> str:
        return (
            f"<ModelFieldSort(FieldName={self.model_field.field_name}, "
            f"Direction={self.direction.name})>"
        )


class ModelFieldOperation(object):
    def __init__(self, model_field: "ModelField", operation: Operator, value: Any):
        self.model_field = model_field
        self.operation = operation
        self.value = value

    def __repr__(self) -> str:
        return (
            "<ModelFieldOperation("
            + f"{self.model_field.field_name} {self.operation} {self.value}"
            ")>"
        )

    @staticmethod
    def to_mongo_filter(
        filters: "List[Union[ModelFieldOperation, CompoundFilter]]",
    ) -> Dict[str, Any]:
        filter_dict: Dict[str, Any] = {}

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


_OP_MAP: Dict[Operator, str] = {
    Operator.EQUAL: "$eq",
    Operator.NOT_EQUAL: "$ne",
    Operator.GREATER_THAN: "$gt",
    Operator.GREATER_THAN_EQUAL: "$gte",
    Operator.LESS_THAN: "$lt",
    Operator.LESS_THAN_EQUAL: "$lte",
    Operator.IN: "$in",
    Operator.NOT_IN: "$nin",
}


def _op_to_expr(op: "ModelFieldOperation") -> Dict[str, Any]:
    """Return the MongoDB operator expression for one op (without the field name)."""
    if op.operation in _OP_MAP:
        return {_OP_MAP[op.operation]: op.value}
    if op.operation == Operator.BETWEEN:
        low, high = op.value
        return {"$gte": low, "$lte": high}
    if op.operation == Operator.REGEX:
        expr: Dict[str, Any] = {"$regex": op.value.pattern}
        if op.value.options:
            expr["$options"] = op.value.options
        return expr
    raise NotImplementedError(f"No MongoDB expression for operator {op.operation}")


def _single_op_to_filter(op: "ModelFieldOperation") -> Dict[str, Any]:
    """Convert a single ModelFieldOperation to ``{field: {mongo_op: value}}``."""
    return {op.model_field.field_name: _op_to_expr(op)}


class CompoundFilter:
    """Represents logical compound filters: $or, $and, $nor, or field-level $not."""

    def __init__(
        self,
        op: str,
        children: "List[Union[ModelFieldOperation, CompoundFilter]]",
    ):
        self.op = op
        self._children = children

    def __repr__(self) -> str:
        return f"<CompoundFilter(op={self.op}, n_children={len(self._children)})>"

    def to_mongo_filter(self) -> Dict[str, Any]:
        # Special case: field-level $not wrapping a single ModelFieldOperation
        if self.op == "$not_field":
            child = self._children[0]
            assert isinstance(child, ModelFieldOperation)
            return {child.model_field.field_name: {"$not": _op_to_expr(child)}}

        child_filters: List[Dict[str, Any]] = []
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


def _like_to_regex(pattern: str) -> str:
    """Convert a SQL LIKE pattern to an anchored regex string.

    ``%`` → ``.*``, ``_`` → ``.``, all other chars are ``re.escape``-d.
    """
    parts: List[str] = []
    for ch in pattern:
        if ch == "%":
            parts.append(".*")
        elif ch == "_":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    return "^" + "".join(parts) + "$"


class Mapped(Generic[_T_field]):
    """ORM-instrumented attribute descriptor.

    Class-level access (``User.name``) returns this descriptor — with
    comparison and method operators that build ``ModelFieldOperation``.
    Instance-level access (``user.name``) returns the underlying value of
    type ``_T_field``.

    Declare model fields with ``Mapped[T]`` and ``mapped_field()`` to get
    full IDE / pyright support for query operators (``in_``, ``like``,
    ``between``, ``==``, etc.).
    """

    __slots__ = ("_field_name", "_owner")

    def __init__(self) -> None:
        self._field_name: str = ""
        self._owner: Optional[type] = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._field_name = name
        self._owner = owner

    @overload
    def __get__(self, instance: None, owner: type) -> "Mapped[_T_field]": ...
    @overload
    def __get__(self, instance: object, owner: type) -> _T_field: ...
    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        return instance.__dict__[self._field_name]

    def __set__(self, instance: Any, value: _T_field) -> None:
        # Delegate so Pydantic's validate_assignment hook runs.
        BaseModel.__setattr__(instance, self._field_name, value)

    def __hash__(self) -> int:
        return id(self)

    # ── comparison operators ────────────────────────────────────────────────
    def __eq__(self, other: object) -> "ModelFieldOperation":  # type: ignore[override]
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.EQUAL,
            value=other,
        )

    def __ne__(self, other: object) -> "ModelFieldOperation":  # type: ignore[override]
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.NOT_EQUAL,
            value=other,
        )

    def __gt__(self, other: object) -> "ModelFieldOperation":
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.GREATER_THAN,
            value=other,
        )

    def __ge__(self, other: object) -> "ModelFieldOperation":
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.GREATER_THAN_EQUAL,
            value=other,
        )

    def __lt__(self, other: object) -> "ModelFieldOperation":
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.LESS_THAN,
            value=other,
        )

    def __le__(self, other: object) -> "ModelFieldOperation":
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.LESS_THAN_EQUAL,
            value=other,
        )

    def __neg__(self) -> "ModelFieldSort":
        return ModelFieldSort(model_field=self, direction=SortDirection.DESC)

    # ── method operators ────────────────────────────────────────────────────
    def in_(self, values: Iterable[Any]) -> "ModelFieldOperation":
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.IN,
            value=values,
        )

    def not_in(self, values: Iterable[Any]) -> "ModelFieldOperation":
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.NOT_IN,
            value=values,
        )

    def is_(self, value: object) -> "ModelFieldOperation":
        """Equality (supports ``None`` for null check)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.EQUAL,
            value=value,
        )

    def is_not(self, value: object) -> "ModelFieldOperation":
        """Negated equality (supports ``None``)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.NOT_EQUAL,
            value=value,
        )

    def like(self, pattern: str) -> "ModelFieldOperation":
        """SQL LIKE match (``%`` = any chars, ``_`` = one char). Case-sensitive."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=_like_to_regex(pattern)),
        )

    def ilike(self, pattern: str) -> "ModelFieldOperation":
        """Case-insensitive SQL LIKE match."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=_like_to_regex(pattern), options="i"),
        )

    def contains(self, value: str) -> "ModelFieldOperation":
        """Substring match (case-sensitive)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=re.escape(value)),
        )

    def startswith(self, value: str) -> "ModelFieldOperation":
        """Prefix match (case-sensitive)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern="^" + re.escape(value)),
        )

    def endswith(self, value: str) -> "ModelFieldOperation":
        """Suffix match (case-sensitive)."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.REGEX,
            value=RegexValue(pattern=re.escape(value) + "$"),
        )

    def between(self, low: object, high: object) -> "ModelFieldOperation":
        """Inclusive range: ``low <= field <= high``."""
        return ModelFieldOperation(
            model_field=self,
            operation=Operator.BETWEEN,
            value=(low, high),
        )

    # ── name compatibility ─────────────────────────────────────────────────
    @property
    def field_name(self) -> str:
        """Compatibility shim for code that reads ``ModelField.field_name``."""
        return self._field_name

    @property
    def model_class(self) -> Optional[type]:
        """Compatibility shim for code that reads ``ModelField.model_class``.

        ``None`` only when the descriptor was instantiated directly and not
        installed onto a class (typically a unit-test scenario).
        """
        return self._owner

    # ── Pydantic integration ───────────────────────────────────────────────
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        # Unwrap Mapped[T] → T for Pydantic validation/serialization.
        args = get_args(source_type)
        if not args:
            return core_schema.any_schema()
        return handler(args[0])


# Backward-compat alias. ``ModelField`` was a separate class in v0.5; v0.6
# unifies it with ``Mapped[Any]`` so existing internals (Select projection
# lists, ModelFieldSort/ModelFieldOperation.model_field, etc.) keep working
# unchanged.
ModelField = Mapped[Any]


class MongoFieldInfo(FieldInfo):  # type: ignore[misc]
    """Extends ``pydantic.fields.FieldInfo`` with Mongo-specific metadata.

    The ``# type: ignore[misc]`` is required because Pydantic v2 marks
    ``FieldInfo`` with ``@final`` for type checkers. Runtime allows
    subclassing, and Pydantic's own internals subclass ``FieldInfo`` in
    places too.
    """

    __slots__ = ("index", "unique", "sparse")

    def __init__(
        self,
        *,
        index: bool = False,
        unique: bool = False,
        sparse: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.index = index
        self.unique = unique
        self.sparse = sparse


def mapped_field(
    default: Any = PydanticUndefined,
    *,
    default_factory: Optional[Callable[[], Any]] = None,
    alias: Optional[str] = None,
    validation_alias: Optional[str] = None,
    serialization_alias: Optional[str] = None,
    description: Optional[str] = None,
    examples: Optional[List[Any]] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    multiple_of: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
    index: bool = False,
    unique: bool = False,
    sparse: bool = False,
    **kwargs: Any,
) -> Any:
    """Mongotic field declaration. Wraps Pydantic ``Field()`` and adds Mongo
    extras (``index`` / ``unique`` / ``sparse``).

    Returns ``Any`` (not ``MongoFieldInfo``) so the result is assignable to a
    ``Mapped[T]`` annotation without type-checker complaint.
    """
    return MongoFieldInfo(
        default=default,
        default_factory=default_factory,
        alias=alias,
        validation_alias=validation_alias,
        serialization_alias=serialization_alias,
        description=description,
        examples=examples,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        index=index,
        unique=unique,
        sparse=sparse,
        **kwargs,
    )


class MongoBaseModelMeta(_model_construction.ModelMetaclass):
    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: Dict[str, Any],
        **kwargs: Any,
    ) -> "MongoBaseModelMeta":
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # After Pydantic processes annotated fields, install a Mapped descriptor
        # for each so class-level attribute access yields a typed query
        # expression (User.name → Mapped[str]) while instance access still
        # returns the underlying value (user.name → str).
        model_fields: Dict[str, FieldInfo] = cls.model_fields  # type: ignore[attr-defined]
        for field_name, field_info in model_fields.items():
            existing = namespace.get(field_name)
            if not isinstance(existing, Mapped):
                descriptor: Mapped = Mapped()
                descriptor.__set_name__(cls, field_name)
                setattr(cls, field_name, descriptor)
            # Emit a DeprecationWarning for fields declared with plain
            # pydantic.Field() instead of mongotic.mapped_field(). The runtime
            # still works (descriptor was installed above), but IDE / pyright
            # cannot see Mapped-style typing on the field.
            if (
                field_info is not None
                and not isinstance(field_info, MongoFieldInfo)
                and not _is_inherited_field(field_name, bases)
            ):
                warnings.warn(
                    (
                        f"{name}.{field_name} is declared with pydantic.Field() "
                        f"(or has no explicit field info) and will lose IDE "
                        f"support for query operators (.in_, .like, .between, "
                        f"etc.). Migrate to: "
                        f"{field_name}: Mapped[...] = mapped_field(...). "
                        f"This compatibility shim is planned for removal in "
                        f"v0.7.0."
                    ),
                    DeprecationWarning,
                    stacklevel=2,
                )
        return cls


def _is_inherited_field(field_name: str, bases: tuple) -> bool:
    """A field already declared (and warned about) on a base class should not
    trigger another warning when the subclass is constructed."""
    for base in bases:
        base_fields = getattr(base, "model_fields", None)
        if base_fields and field_name in base_fields:
            return True
    return False


class MongoBaseModel(BaseModel, metaclass=MongoBaseModelMeta):
    __databasename__: str = NOT_SET_SENTINEL  # type: ignore[assignment]
    __tablename__: str = NOT_SET_SENTINEL  # type: ignore[assignment]
    __indexes__: ClassVar[List[Any]] = []

    _id: Optional[str] = PrivateAttr(None)
    _session: Optional["Session"] = PrivateAttr(None)
    _expired: bool = PrivateAttr(default=False)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if self._session is not None and name not in ["_id", "_session"]:
            self._session._update_instances[(id(self), name)] = (self, name, value)
