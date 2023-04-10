"""Inventory test methods"""
from unittest.mock import AsyncMock

from pytest import mark

from jshell.core.inventory import Inventory


@mark.asyncio
async def test_run() -> None:
    """Calling run on inventory should call the corresponding task on hosts."""
    inventory = Inventory()
    deploy_mock = AsyncMock()

    @inventory.task("otters")
    async def deploy() -> None:
        await deploy_mock()

    await inventory.run("deploy")
    deploy_mock.assert_awaited_once_with()

    deploy_mock.reset_mock()
    await inventory.run("otters")
    deploy_mock.assert_awaited_once_with()

    deploy_mock.reset_mock()
    await inventory.run("badgers")
    deploy_mock.assert_not_awaited()
