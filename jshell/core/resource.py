from asyncio import Lock
from types import TracebackType
from typing import AsyncContextManager, Callable, Generic, TypeVar

T = TypeVar("T")


class Resource(Generic[T]):
    def __init__(self, loader: Callable[[], AsyncContextManager[T]]) -> None:
        self._loader = loader
        self._context_manager: AsyncContextManager[T] | None = None
        self._resource: T | None = None
        self._lock = Lock()
        self._acquire_count = 0

    async def __aenter__(self) -> T:
        async with self._lock:
            if self._context_manager is None:
                assert self._resource is None
                self._context_manager = self._loader()
                self._resource = await self._context_manager.__aenter__()
            self._acquire_count = self._acquire_count + 1
        assert self._resource is not None
        return self._resource

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        async with self._lock:
            self._acquire_count = self._acquire_count - 1
            if self._acquire_count == 0:
                assert self._context_manager is not None
                await self._context_manager.__aexit__(exc_type, exc_val, exc_tb)
                self._context_manager = None
                self._resource = None
