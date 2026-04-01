"""Pydantic-style request/response schemas for v1 endpoints."""

from dataclasses import dataclass, field


@dataclass
class UserCreateRequest:
    """Payload for creating a new user."""

    username: str
    email: str
    roles: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return a list of validation error messages, empty if valid."""
        errors: list[str] = []
        if not self.username.strip():
            errors.append("username must not be blank")
        if "@" not in self.email:
            errors.append("email must contain @")
        return errors


@dataclass
class UserResponse:
    """Serialised user data returned to callers."""

    id: int
    username: str
    email: str
    is_active: bool
    roles: list[str] = field(default_factory=list)


@dataclass
class ErrorResponse:
    code: int
    message: str
    detail: str = ""
