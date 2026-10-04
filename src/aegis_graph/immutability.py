"""Deep-freezing helpers for persisted semantic/evidence value objects."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from copy import deepcopy
from typing import Any, TypeVar, cast

_T = TypeVar("_T")


class FrozenMapping(Mapping[str, Any]):
    """Small immutable mapping safe under deepcopy/dataclasses.asdict."""

    __slots__ = ("_items",)
    _items: tuple[tuple[str, Any], ...]

    def __init__(self, items: tuple[tuple[str, Any], ...]) -> None:
        object.__setattr__(self, "_items", items)

    def __getitem__(self, key: str) -> Any:
        for item_key, value in self._items:
            if item_key == key:
                # Never expose a retained mutable extension object by reference.
                # Known containers are already recursively frozen; deepcopy is a
                # no-op for immutable scalars and defensive for custom values.
                return deepcopy(value)
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise TypeError("frozen semantic data may not be mutated")

    def __deepcopy__(self, _memo: dict[int, Any]) -> FrozenMapping:
        return self

    def __repr__(self) -> str:
        return repr(dict(self._items))


def _freeze_value(item: Any, active: set[int]) -> Any:
    if isinstance(item, Mapping):
        identity = id(item)
        if identity in active:
            raise ValueError("cyclic semantic data is not supported")
        active.add(identity)
        try:
            frozen_items: list[tuple[str, Any]] = []
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise TypeError("semantic data keys must be strings")
                if not key.strip():
                    raise ValueError("semantic data keys must be non-empty strings")
                frozen_items.append((key, _freeze_value(nested, active)))
            return FrozenMapping(tuple(frozen_items))
        finally:
            active.remove(identity)
    if isinstance(item, (list, tuple)):
        identity = id(item)
        if identity in active:
            raise ValueError("cyclic semantic data is not supported")
        active.add(identity)
        try:
            return tuple(_freeze_value(nested, active) for nested in item)
        finally:
            active.remove(identity)
    if isinstance(item, (set, frozenset)):
        identity = id(item)
        if identity in active:
            raise ValueError("cyclic semantic data is not supported")
        active.add(identity)
        try:
            return frozenset(_freeze_value(nested, active) for nested in item)
        finally:
            active.remove(identity)
    try:
        return deepcopy(item)
    except Exception as exc:
        raise TypeError(
            f"semantic data value of type {type(item).__name__} cannot be snapshotted"
        ) from exc


def freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Detach/freeze nested containers and reject ambiguous or cyclic mappings."""

    frozen = _freeze_value(value, set())
    if not isinstance(frozen, Mapping):
        raise TypeError("semantic data must be a mapping")
    return frozen


def freeze_tuple(value: Iterable[_T]) -> tuple[_T, ...]:
    """Snapshot a sequence recursively as a tuple without retaining mutable aliases."""

    if isinstance(value, (str, bytes, bytearray, memoryview)):
        raise TypeError("semantic sequence must be an iterable of values, not scalar data")
    frozen = _freeze_value(value, set())
    if not isinstance(frozen, tuple):
        raise TypeError("semantic sequence must be tuple-compatible")
    return cast(tuple[_T, ...], frozen)
