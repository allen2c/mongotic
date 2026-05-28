"""Tests for v0.6 Mapped[T] descriptor and mapped_field() factory."""

from typing import List, Optional

import pytest
from pydantic import ConfigDict, PrivateAttr, ValidationError

from mongotic import Mapped, MongoBaseModel, MongoFieldInfo, mapped_field
from mongotic.model import ModelFieldOperation


class _U(MongoBaseModel):
    __databasename__ = "test"
    __tablename__ = "v06_mapped_users"

    name: Mapped[str] = mapped_field(min_length=2)
    age: Mapped[int] = mapped_field(default=0, ge=0, le=150)
    email: Mapped[Optional[str]] = mapped_field(default=None, unique=True)
    tags: Mapped[List[str]] = mapped_field(default_factory=list, index=True)


def test_class_level_access_returns_mapped() -> None:
    assert isinstance(_U.name, Mapped)
    assert isinstance(_U.age, Mapped)
    assert isinstance(_U.email, Mapped)
    assert isinstance(_U.tags, Mapped)


def test_instance_level_access_returns_value_type() -> None:
    u = _U(name="alice", age=30, email="a@x.com")
    assert isinstance(u.name, str) and u.name == "alice"
    assert isinstance(u.age, int) and u.age == 30
    assert isinstance(u.email, str) and u.email == "a@x.com"
    assert isinstance(u.tags, list) and u.tags == []
    assert u.name.upper() == "ALICE"


def test_comparison_operators() -> None:
    assert isinstance(_U.name == "x", ModelFieldOperation)
    assert isinstance(_U.name != "x", ModelFieldOperation)
    assert isinstance(_U.age > 18, ModelFieldOperation)
    assert isinstance(_U.age >= 18, ModelFieldOperation)
    assert isinstance(_U.age < 100, ModelFieldOperation)
    assert isinstance(_U.age <= 100, ModelFieldOperation)


def test_method_operators() -> None:
    for op in [
        _U.name.in_(["a", "b"]),
        _U.name.not_in(["c"]),
        _U.email.is_(None),
        _U.email.is_not(None),
        _U.name.like("a%"),
        _U.name.ilike("A%"),
        _U.name.contains("li"),
        _U.name.startswith("al"),
        _U.name.endswith("ce"),
        _U.age.between(18, 65),
    ]:
        assert isinstance(op, ModelFieldOperation)


def test_pydantic_validation_runs() -> None:
    with pytest.raises(ValidationError):
        _U(name="a")
    with pytest.raises(ValidationError):
        _U(name="alice", age=200)
    with pytest.raises(ValidationError):
        _U(name="alice", age=-1)


def test_inheritance_installs_descriptors_on_subclass() -> None:
    class _Admin(_U):
        role: Mapped[str] = mapped_field(default="admin")

    assert isinstance(_Admin.name, Mapped)
    assert isinstance(_Admin.role, Mapped)
    a = _Admin(name="root", role="su")
    assert a.role == "su"
    assert isinstance(_Admin.role == "su", ModelFieldOperation)


def test_validate_assignment_triggers_on_mutation() -> None:
    class _Strict(MongoBaseModel):
        model_config = ConfigDict(validate_assignment=True)
        __databasename__ = "test"
        __tablename__ = "v06_strict"

        name: Mapped[str] = mapped_field(min_length=2)
        age: Mapped[int] = mapped_field(ge=0, le=150)

    s = _Strict(name="alice", age=30)
    s.age = 99
    assert s.age == 99
    with pytest.raises(ValidationError):
        s.age = 200
    with pytest.raises(ValidationError):
        s.name = "a"
    with pytest.raises(ValidationError):
        s.age = "not a number"  # type: ignore[assignment]


def test_private_attr_coexists() -> None:
    class _Tracked(MongoBaseModel):
        __databasename__ = "test"
        __tablename__ = "v06_tracked"

        name: Mapped[str] = mapped_field()
        _internal: int = PrivateAttr(default=0)

    t = _Tracked(name="x")
    assert t._internal == 0
    object.__setattr__(t, "_internal", 42)
    assert t._internal == 42
    assert t.name == "x"
    assert isinstance(_Tracked.name, Mapped)


def test_forward_ref_annotation() -> None:
    class _Node(MongoBaseModel):
        __databasename__ = "test"
        __tablename__ = "v06_nodes"

        name: Mapped[str] = mapped_field()
        children_ids: Mapped["List[str]"] = mapped_field(default_factory=list)

    n = _Node(name="root", children_ids=["a", "b"])
    assert n.children_ids == ["a", "b"]
    assert isinstance(_Node.children_ids, Mapped)


def test_mongo_field_info_extras() -> None:
    name_info = _U.model_fields["name"]
    assert isinstance(name_info, MongoFieldInfo)
    assert name_info.index is False
    assert name_info.unique is False

    email_info = _U.model_fields["email"]
    assert isinstance(email_info, MongoFieldInfo)
    assert email_info.unique is True

    tags_info = _U.model_fields["tags"]
    assert isinstance(tags_info, MongoFieldInfo)
    assert tags_info.index is True


def test_model_dump_includes_only_field_values() -> None:
    u = _U(name="alice", age=30, email="a@x.com", tags=["t"])
    dumped = u.model_dump()
    assert dumped == {"name": "alice", "age": 30, "email": "a@x.com", "tags": ["t"]}


def test_json_schema_propagates_constraints() -> None:
    schema = _U.model_json_schema()
    name_schema = schema["properties"]["name"]
    assert name_schema.get("minLength") == 2
    age_schema = schema["properties"]["age"]
    assert age_schema.get("minimum") == 0
    assert age_schema.get("maximum") == 150


def test_legacy_field_declaration_emits_deprecation_warning() -> None:
    from pydantic import Field

    with pytest.warns(
        DeprecationWarning,
        match=r"\.legacy_name is declared with pydantic\.Field",
    ):

        class _Legacy(MongoBaseModel):
            __databasename__ = "test"
            __tablename__ = "v06_legacy"

            legacy_name: str = Field(...)

    # Runtime still works (descriptor installed despite legacy declaration)
    obj = _Legacy(legacy_name="x")
    assert obj.legacy_name == "x"
    assert isinstance(_Legacy.legacy_name, Mapped)
