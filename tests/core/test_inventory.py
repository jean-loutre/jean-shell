"""Inventory test methods"""
from dataclasses import dataclass
from unittest.mock import AsyncMock

from pytest import mark

from jshell.core.inventory import Inventory, Target, task


@mark.asyncio
async def test_run() -> None:
    """Calling run on inventory should call the corresponding task on hosts."""

    deploy_mock = AsyncMock()
    peter = Target(name="peter", tasks={"deploy": deploy_mock})
    inventory = Inventory(targets=[peter])

    await inventory.run("deploy")
    deploy_mock.assert_awaited_once_with(inventory)


@mark.asyncio
async def test_task_decorator() -> None:
    """Methods decorated with the @task decorator should be inserted in a target task list."""

    deploy_mock = AsyncMock()

    @dataclass(frozen=True)
    class _Peter(Target):
        name: str = "peter"

        @task
        async def deploy(self, inventory: Inventory) -> None:
            """deploy peter."""
            await deploy_mock(self, inventory)

    peter = _Peter()
    inventory = Inventory(targets=[peter])

    await inventory.run("deploy")
    deploy_mock.assert_awaited_once_with(peter, inventory)
