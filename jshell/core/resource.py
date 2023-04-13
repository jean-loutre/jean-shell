"""Resource allow to share objects while managing their lifetimes.

Resource are reusable shared context managers. A resource is acquired, by entering it's
context using 'async with'. The first client acquiring a resource will initialize it,
and the last to release it (by exiting the context) will cleanup it. If the same
resource is acquired again, it will be initialized again.

This allows to introduce a dependency chain during task execution : resource can acquire
other resource in their initialization method, leading to an initialization chain, where
each resource can be used by mulitples clients while being initialized only once.
"""
from abc import ABC, abstractmethod
from asyncio import Lock
from contextlib import asynccontextmanager
from functools import wraps
from types import TracebackType
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Callable,
    Generic,
    ParamSpec,
    TypeVar,
    cast,
)

T = TypeVar("T")


class Resource(ABC, Generic[T]):
    """Abstract base class for resource.

    Resource initialization must be implemented in the _init method, cleanup in the
    _cleanup method, as their name strongly suggests. Resource behaves like an async
    context manager, calling _init and _cleanup only once for all parallel __aenter__
    and __aexit__ calls.

    Resources are reusable, so implementation must take into account that multiple _init
    / _cleanup sequence can be called on the same object."""

    def __init__(self) -> None:
        """Initialize the resource context."""
        self._resource: T | None = None
        self._lock = Lock()
        self._acquire_count = 0

    @abstractmethod
    async def _init(self) -> T:
        """Initialize the underyling resource."""

    @abstractmethod
    async def _cleanup(self) -> None:
        """Cleanup the underyling resource."""

    async def __aenter__(self) -> T:
        async with self._lock:
            if self._acquire_count == 0:
                assert self._resource is None
                self._resource = await self._init()
            self._acquire_count = self._acquire_count + 1
        # need the cast, as T can be a union containing None, so we can't assert
        # resource is not None here.
        return cast(T, self._resource)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        async with self._lock:
            self._acquire_count = self._acquire_count - 1
            if self._acquire_count == 0:
                await self._cleanup()
                self._resource = None


class AsyncContextManagerResource(Resource[T]):
    """Wrap an async context manager into a resource.

    Will create and enter the underlying context manager only once for all parallel
    resource acquisition.
    """

    def __init__(self, context_factory: Callable[[], AsyncContextManager[T]]) -> None:
        """Initialize the ContextManagerResource.

        Args:
            context_factory:
                Callable returning an AsyncContextManager that will be entered on _init,
                and exited on _cleanup. The factory will be called again to create a new
                context if the resource is acquired again after having been released.

        """
        super().__init__()
        self._context_factory = context_factory
        self._context: AsyncContextManager[T] | None = None

    async def _init(self) -> T:
        assert self._context is None
        self._context = self._context_factory()
        return await self._context.__aenter__()

    async def _cleanup(self) -> None:
        assert self._context is not None
        await self._context.__aexit__(None, None, None)
        self._context = None


P = ParamSpec("P")


def resource(func: Callable[P, AsyncIterator[T]]) -> Callable[P, Resource[T]]:
    """Decorator to wrap a function returning an async itorator into a resource.

    The wrapped function will behave the same way it was wrapped in an async context
    manager, except that it will be entered / exited only once for each parallel call on
    the returned Resource.

    Warning:
        Each call to the resulting function will create an independent resource, meaning
        that you should call 'async with' several time on the returned value, and not
        call several times the function :

        ```
        @resource async def my_resource():
            yield value
        resource = my_resource()

        ...

        def parallel_function():
            async with resource as value:
                ...
        ```

        **and not** :

        ```
        @resource async def my_resource():
            yield value
        ...

        def parallel_function():
            # This will enter / exit my_resource at each call
            async with my_resource() as value:
                ...
        ```
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Resource[T]:
        @asynccontextmanager
        async def _context_factory() -> AsyncIterator[T]:
            async for it in func(*args, **kwargs):
                yield it

        return AsyncContextManagerResource(_context_factory)

    return wrapper
