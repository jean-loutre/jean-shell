from contextlib import asynccontextmanager
from typing import AsyncIterator
from unittest.mock import Mock

from jshell.core.resource import AsyncContextManagerResource, Resource, resource


async def test_acquire_release() -> None:
    load = Mock()
    cleanup = Mock()

    class _MockResource(Resource[object]):
        async def _init(self) -> object:
            load()
            return object()

        async def _cleanup(self) -> None:
            cleanup()

    resource = _MockResource()

    async with resource as value_1:
        load.assert_called_once()
        cleanup.assert_not_called()

        async with resource as value_2:
            load.assert_called_once()
            assert value_1 == value_2
            cleanup.assert_not_called()

        cleanup.assert_not_called()

    cleanup.assert_called_once()


async def test_async_context_manager_resource() -> None:
    load = Mock()
    cleanup = Mock()

    @asynccontextmanager
    async def _load() -> AsyncIterator[object]:
        load()
        yield object()
        cleanup()

    async with AsyncContextManagerResource(_load):
        load.assert_called_once()
        cleanup.assert_not_called()

    cleanup.assert_called_once()


async def test_resource_decorator() -> None:
    load = Mock()
    cleanup = Mock()

    @resource
    async def test_resource() -> AsyncIterator[object]:
        load()
        yield object()
        cleanup()

    async with test_resource():
        load.assert_called_once()
        cleanup.assert_not_called()

    cleanup.assert_called_once()
