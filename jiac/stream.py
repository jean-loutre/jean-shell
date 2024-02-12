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
        ...

    async def close(self) -> None:
        ...


class MemoryStream:
    """Stream implementation writing to a bytarray"""

    def __init__(self, buffer: bytearray | None = None) -> None:
        """Initialize the memory stream.

        Args:
            buffer: The bytarray to write to. If none, a new bytearray will be
                    created.
        """
        self._buffer = buffer if buffer is not None else bytearray()

    @property
    def buffer(self) -> bytearray:
        return self._buffer

    async def write(self, data: bytes) -> None:
        self._buffer.extend(data)

    async def close(self) -> None:
        ...
