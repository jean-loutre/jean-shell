from jiac import task, Task
from asyncio import sleep
from unittest.mock import AsyncMock
from typing import AsyncIterator
from contextlib import asynccontextmanager


async def test_chain_tasks() -> None:
    take_dinglepop_mock = AsyncMock(return_value="dinglepop")
    take_dinglepop = task()(take_dinglepop_mock)

    smooth_dinglepop_mock = AsyncMock()
    smooth_dinglepop = task()(smooth_dinglepop_mock)

    dinglepop = take_dinglepop()
    await Task.run([smooth_dinglepop(dinglepop, dinglepop, "schleems")])

    # Should've been awaited only once
    take_dinglepop_mock.assert_awaited_once()
    smooth_dinglepop_mock.assert_awaited_once_with("dinglepop", "dinglepop", "schleems")


async def test_async_context_manager_task() -> None:
    sequence = []

    @task()
    @asynccontextmanager
    async def take_dinglepop() -> AsyncIterator[str]:
        sequence.append("one")
        yield "dinglepop"
        sequence.append("three")

    @task()
    async def smooth_dinglepop(dinglepop: str) -> None:
        assert dinglepop == "dinglepop"
        sequence.append("two")

    await Task.run([smooth_dinglepop(take_dinglepop())])

    assert sequence == ["one", "two", "three"]


async def test_explicit_dependencies() -> None:
    sequence = []

    @task()
    async def take_dinglepop() -> None:
        await sleep(0.1)
        sequence.append("one")

    @task()
    async def smooth_dinglepop() -> str:
        sequence.append("two")
        return "smoothed dinglepop"

    @task()
    async def rub_shleem(dinglepop: str) -> None:
        assert dinglepop == "smoothed dinglepop"

    smooth_task = take_dinglepop().then(smooth_dinglepop())
    await Task.run([rub_shleem(smooth_task)])

    assert sequence == ["one", "two"]

    sequence.clear()
    # alternative form
    smooth_task = take_dinglepop() & smooth_dinglepop()
    await Task.run([rub_shleem(smooth_task)])

    assert sequence == ["one", "two"]
