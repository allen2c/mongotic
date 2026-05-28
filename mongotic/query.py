from __future__ import annotations

from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from mongotic.model import (
    FilterType,
    ModelField,
    ModelFieldSort,
    MongoBaseModel,
    SortDirection,
)

_T = TypeVar("_T", bound=MongoBaseModel)


def _is_model_entity(e: object) -> bool:
    from mongotic.model import MongoBaseModel

    return isinstance(e, type) and issubclass(e, MongoBaseModel)


def _is_field_entity(e: object) -> bool:
    from mongotic.model import Mapped

    return isinstance(e, Mapped)


class Select(Generic[_T]):
    def __init__(
        self,
        entities: Tuple[Union[Type[MongoBaseModel], ModelField], ...],
    ) -> None:

        if not entities:
            raise TypeError("select() requires at least one entity")

        self._model: Type[MongoBaseModel]
        self._projection_fields: List[ModelField]
        if all(_is_model_entity(e) for e in entities):
            if len(entities) > 1:
                raise TypeError(
                    "select() supports only a single model entity at a time"
                )
            first = next(iter(entities))
            assert isinstance(first, type)
            self._model = first
            self._projection_fields = []
        elif all(_is_field_entity(e) for e in entities):
            from mongotic.model import Mapped

            fields = [e for e in entities if isinstance(e, Mapped)]
            owners = {f.model_class for f in fields if f.model_class is not None}
            if len(owners) > 1:
                raise TypeError(
                    f"select() projection fields must belong to one model, got {owners!r}"
                )
            self._model = next(iter(owners))
            self._projection_fields = fields
        else:
            raise TypeError(
                f"select() entities must be either a MongoBaseModel subclass or "
                f"all ModelField instances, not a mix: {entities!r}"
            )

        self._projection_field_names = [f.field_name for f in self._projection_fields]
        self._filters: List[FilterType] = []
        self._sort: List[ModelFieldSort] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._distinct_field: Optional[ModelField] = None
        self._yield_per: Optional[int] = None

    @property
    def is_projection(self) -> bool:
        return bool(self._projection_fields)

    @property
    def projection_field_names(self) -> List[str]:
        return self._projection_field_names

    @property
    def projection_field_count(self) -> int:
        return len(self._projection_fields)

    def where(self, *conditions: FilterType) -> Select[_T]:
        self._filters.extend(conditions)
        return self

    def distinct(self, field: ModelField) -> Select[_T]:
        """Return unique values for *field* using MongoDB ``collection.distinct()``.

        Call ``.all()`` on the resulting ``ScalarResult`` to retrieve a
        ``List[Any]`` of distinct values.

        Note: ``.order_by()``, ``.limit()``, and ``.offset()`` are ignored for
        distinct queries — MongoDB's ``distinct`` command does not support them.
        """
        self._distinct_field = field
        return self

    def order_by(self, *fields: Union[ModelFieldSort, ModelField]) -> Select[_T]:
        from mongotic.model import Mapped

        for field in fields:
            if isinstance(field, ModelFieldSort):
                self._sort.append(field)
            elif isinstance(field, Mapped):
                self._sort.append(
                    ModelFieldSort(model_field=field, direction=SortDirection.ASC)
                )
            else:
                raise TypeError(
                    f"order_by expects ModelField or -ModelField, got {type(field)}"
                )
        return self

    def limit(self, value: int) -> Select[_T]:
        if value < 0:
            raise ValueError("Limit value must be non-negative")
        self._limit = value
        return self

    def offset(self, value: int) -> Select[_T]:
        if value < 0:
            raise ValueError("Offset value must be non-negative")
        self._offset = value
        return self

    def yield_per(self, n: int) -> Select[_T]:
        """API-compatible with SQLAlchemy. PyMongo cursors are already lazy and batched;
        this method is a no-op in mongotic. The parameter is stored so SA-style code
        ports cleanly."""
        self._yield_per = int(n)
        return self


class Update:
    def __init__(self, orm_model: Type[MongoBaseModel]):
        self._model = orm_model
        self._filters: List[FilterType] = []
        self._values: Dict[str, Any] = {}

    def where(self, *conditions: FilterType) -> Update:
        self._filters.extend(conditions)
        return self

    def values(self, **kwargs: Any) -> Update:
        self._values.update(kwargs)
        return self


class Delete:
    def __init__(self, orm_model: Type[MongoBaseModel]):
        self._model = orm_model
        self._filters: List[FilterType] = []

    def where(self, *conditions: FilterType) -> Delete:
        self._filters.extend(conditions)
        return self


class Insert:
    def __init__(self, orm_model: Type[MongoBaseModel]):
        self._model = orm_model
        self._values: List[Dict[str, Any]] = []

    def values(
        self,
        data: Union[
            MongoBaseModel,
            Dict[str, Any],
            List[Union[MongoBaseModel, Dict[str, Any]]],
            None,
        ],
    ) -> Insert:
        if data is None:
            normalized: List[Any] = []
        elif isinstance(data, MongoBaseModel):
            normalized = [data]
        elif isinstance(data, dict):
            normalized = [data]
        elif isinstance(data, list):
            normalized = data  # no copy needed; we only read it
        else:
            raise TypeError(
                f"insert().values() expects dict, list, or MongoBaseModel, got {type(data).__name__}"
            )

        dumps: List[Dict[str, Any]] = []
        for item in normalized:
            if isinstance(item, MongoBaseModel):
                dumps.append(item.model_dump())
            elif isinstance(item, dict):
                # Validate through Pydantic so tracebacks point at user code
                dumps.append(self._model(**item).model_dump())
            else:
                raise TypeError(
                    f"insert().values() list items must be dict or MongoBaseModel, got {type(item).__name__}"
                )
        self._values = dumps
        return self


@overload
def select(model: Type[_T], /) -> Select[_T]: ...
@overload
def select(*fields: ModelField) -> Select[Any]: ...
def select(
    *entities: Union[Type[MongoBaseModel], ModelField],
) -> Select:
    if not entities:
        raise TypeError("select() requires at least one entity")
    return Select(entities=entities)


def update(orm_model: Type[MongoBaseModel]) -> Update:
    return Update(orm_model=orm_model)


def delete(orm_model: Type[MongoBaseModel]) -> Delete:
    return Delete(orm_model=orm_model)


def insert(orm_model: Type[MongoBaseModel]) -> Insert:
    return Insert(orm_model=orm_model)


# ── shared helpers ────────────────────────────────────────────────────────────


def _compile_sort(sort_list: List[ModelFieldSort]) -> List[Tuple[str, int]]:
    """Convert internal sort entries to pymongo (field, direction) tuples."""
    from pymongo import ASCENDING, DESCENDING

    from mongotic.model import SortDirection

    return [
        (
            s.model_field.field_name,
            ASCENDING if s.direction == SortDirection.ASC else DESCENDING,
        )
        for s in sort_list
    ]


def _apply_cursor_modifiers(cursor, stmt):
    """Apply sort/skip/limit from a Select to a pymongo cursor (sync or async).
    Returns the modified cursor."""
    if stmt._sort:
        cursor = cursor.sort(_compile_sort(stmt._sort))
    if stmt._offset is not None:
        cursor = cursor.skip(stmt._offset)
    if stmt._limit is not None:
        cursor = cursor.limit(stmt._limit)
    return cursor


def _hydrate_doc(model_cls, doc, session):
    """Build a model instance from a Mongo doc and bind it to a session."""
    obj = model_cls(**doc)
    obj._id = str(doc["_id"])
    obj._session = session
    return obj
