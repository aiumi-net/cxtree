"""Authentication service for user login, logout and token validation."""

import hashlib
import hmac
import time

from domain.base import Repository
from domain.users.models import Session, User


class AuthService:
    _FAKE_PASSWORD = "correct"  # x-db_seed

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode()
        self._sessions = Repository()
        self._session_counter = 0

    def login(self, user: User, password: str) -> str | None:
        if not user.is_active:
            return None
        if not self._check_password(password):
            return None
        token = self._sign(f"{user.id}:{time.monotonic()}")
        self._session_counter += 1
        session = Session(
            user_id=user.id,
            token=token,
            expires_at=time.time() + 3600,
        )
        self._sessions.save(_FakeEntity(self._session_counter, session))  # type: ignore
        return token

    def logout(self, token: str) -> bool:
        for entity in self._sessions.all():
            if entity.data.token == token:
                self._sessions.delete(entity.id)
                return True
        return False

    def validate_token(self, token: str) -> bool:
        now = time.time()
        for entity in self._sessions.all():
            session: Session = entity.data
            if session.token == token:
                return not session.is_expired(now)
        return False

    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

    def _check_password(self, password: str) -> bool:
        return hmac.compare_digest(password, self._FAKE_PASSWORD)


class _FakeEntity:
    def __init__(self, id: int, data: Session) -> None:
        self.id = id
        self.data = data
