from __future__ import annotations

from typing import Any, Iterator, List, Optional, Tuple


class Row:
    """Lightweight tuple+name wrapper for projection results. Immutable."""

    __slots__ = ("_values", "_fields", "_map")

    def __init__(self, values: Tuple[Any, ...], fields: Tuple[str, ...]):
        if len(values) != len(fields):
            raise ValueError(
                f"Row: values length {len(values)} != fields length {len(fields)}"
            )
        object.__setattr__(self, "_values", tuple(values))
        object.__setattr__(self, "_fields", tuple(fields))
        object.__setattr__(self, "_map", {f: i for i, f in enumerate(fields)})

    def __getattr__(self, name: str) -> Any:
        _map = object.__getattribute__(self, "_map")
        if name in _map:
            return object.__getattribute__(self, "_values")[_map[name]]
        raise AttributeError(name)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        if isinstance(key, str):
            return self._values[self._map[key]]
        raise TypeError(f"Row indices must be int or str, not {type(key).__name__}")

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def _asdict(self) -> dict:
        return {f: self._values[i] for f, i in self._map.items()}

    def __repr__(self) -> str:
        body = ", ".join(f"{f}={self._values[i]!r}" for f, i in self._map.items())
        return f"Row({body})"

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Row is immutable")


class Result:
    """Base for execute() return values on DML statements."""

    def __init__(self, rowcount: int = 0, inserted_ids: List[str] | None = None):
        self.rowcount = rowcount
        self.inserted_ids = list(inserted_ids) if inserted_ids else []


class SelectResult(Result):
    """Result of session.execute(select(...)) with column projection."""

    def __init__(self, rows: List[Row]):
        super().__init__(rowcount=len(rows))
        self._rows = list(rows)

    def all(self) -> List[Row]:
        return self._rows

    def first(self) -> Optional[Row]:
        return self._rows[0] if self._rows else None

    def one(self) -> Row:
        from mongotic.exceptions import MultipleResultsFound, NotFound

        if not self._rows:
            raise NotFound("No result found")
        if len(self._rows) > 1:
            raise MultipleResultsFound("Expected one result, got multiple")
        return self._rows[0]

    def one_or_none(self) -> Optional[Row]:
        from mongotic.exceptions import MultipleResultsFound

        if not self._rows:
            return None
        if len(self._rows) > 1:
            raise MultipleResultsFound("Expected one result, got multiple")
        return self._rows[0]

    def scalars(self) -> List[Any]:
        if self._rows and len(self._rows[0]) != 1:
            raise TypeError("SelectResult.scalars() requires single-column select")
        return [r[0] for r in self._rows]

    def __iter__(self) -> Iterator[Row]:
        return iter(self._rows)
