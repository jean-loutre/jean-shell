"""Config unit tests."""
from contextlib import asynccontextmanager
from typing import AsyncIterator
from unittest.mock import Mock

from jshell.core.resource import Resource


async def test_acquire_release() -> None:
    """load_from_python should load a class from a python file."""
    load = Mock()
    cleanup = Mock()

    @asynccontextmanager
    async def load_otter() -> AsyncIterator[object]:
        load()
        yield object()
        cleanup()

    otter_resource = Resource(load_otter)

    async with otter_resource as otter_1:
        load.assert_called_once()
        cleanup.assert_not_called()

        async with otter_resource as otter_2:
            load.assert_called_once()
            assert otter_1 == otter_2
            cleanup.assert_not_called()

        cleanup.assert_not_called()

    cleanup.assert_called_once()
