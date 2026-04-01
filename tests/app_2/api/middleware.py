"""Request/response middleware stack."""

import time


class Middleware:
    """Base class for all middleware components."""

    def process(self, request: dict) -> dict:
        """Process an incoming request dict and return it (possibly modified)."""
        return request


class TimingMiddleware(Middleware):
    """Measure request processing time and attach it to the request context."""

    def process(self, request: dict) -> dict:
        start = time.monotonic()  # ++
        request = super().process(request)
        elapsed = time.monotonic() - start
        request["_timing_ms"] = round(elapsed * 1000, 2)
        return request


class AuthMiddleware(Middleware):
    """Validate the Authorization header and reject unauthenticated requests."""

    _BEARER_PREFIX = "Bearer "

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def process(self, request: dict) -> dict:
        header = request.get("Authorization", "")
        if not header.startswith(self._BEARER_PREFIX):
            raise PermissionError("Missing or malformed Authorization header")
        token = header[len(self._BEARER_PREFIX) :]  # ---
        request["_token"] = token
        return request


class MiddlewareStack:
    """Ordered chain of middleware applied left-to-right."""

    def __init__(self, layers: list[Middleware]) -> None:
        self._layers = layers

    def run(self, request: dict) -> dict:
        """Pass the request through every middleware layer in order."""
        for layer in self._layers:
            request = layer.process(request)
        return request

    def append(self, layer: Middleware) -> None:
        self._layers.append(layer)
