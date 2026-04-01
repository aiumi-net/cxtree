"""HTTP route definitions and request dispatching."""

from domain.services import NotificationService, UserService


class Router:
    """Central request router. Maps URL patterns to handler callables."""

    def __init__(self) -> None:
        self._routes: dict[str, object] = {}

    def add(self, path: str, handler: object) -> None:
        """Register a handler for a URL path."""
        self._routes[path] = handler

    def resolve(self, path: str) -> object | None:
        """Return the handler registered for path, or None."""
        return self._routes.get(path)

    def all_paths(self) -> list[str]:
        return list(self._routes.keys())


class UserRouter(Router):
    """Router pre-wired with user CRUD endpoints."""

    def __init__(self, user_svc: UserService) -> None:
        super().__init__()
        self._svc = user_svc
        self._register()

    def _register(self) -> None:
        self.add("/users", self._list)
        self.add("/users/create", self._create)
        self.add("/users/delete", self._delete)

    def _list(self) -> list:
        return self._svc.list_all()

    def _create(self) -> None:
        pass

    def _delete(self) -> None:
        pass


def create_router(
    user_svc: UserService,
    notif_svc: NotificationService,
) -> Router:
    """Build and return the root application router."""
    root = Router()
    user_router = UserRouter(user_svc)
    for path in user_router.all_paths():
        root.add(path, user_router.resolve(path))
    root.add("/notify", notif_svc)
    return root
