from abc import ABC, abstractmethod
from typing import Self
from types import TracebackType


class Stream(ABC):
    @abstractmethod
    async def write(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()


class InputStream(ABC):
    @abstractmethod
    async def read(self, n: int = -1) -> bytes:
        ...


class NullStream:
    async def write(self, _: bytes) -> None:
        pass

    async def close(self) -> None:
        pass
