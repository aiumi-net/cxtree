"""Base classes shared across the domain layer."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    """Root base class for all domain entities.

    Provides a stable identity based on the entity id.
    """

    id: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.id))


class Repository:
    """In-memory repository for storing and retrieving entities."""

    def __init__(self) -> None:
        self._store: dict[int, Any] = {}

    def save(self, entity: Entity) -> None:
        """Persist an entity by its id."""
        self._store[entity.id] = entity

    def get(self, entity_id: int) -> Any | None:
        """Return entity by id, or None if not found."""
        return self._store.get(entity_id)

    def all(self) -> list[Any]:
        """Return all stored entities."""
        return list(self._store.values())

    def delete(self, entity_id: int) -> bool:
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False
