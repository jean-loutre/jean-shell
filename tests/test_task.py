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


async def test_then() -> None:
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


async def test_along_with() -> None:
    take_dinglepop_mock = AsyncMock()
    take_dinglepop = task()(take_dinglepop_mock)()

    smooth_dinglepop_mock = AsyncMock()
    smooth_dinglepop = task()(smooth_dinglepop_mock)()

    # check adding several times the same task does nothing
    await Task.run(
        [smooth_dinglepop.along_with(take_dinglepop).along_with(smooth_dinglepop)]
    )

    take_dinglepop_mock.assert_awaited_once()
    smooth_dinglepop_mock.assert_awaited_once()

    take_dinglepop_mock.reset_mock()
    smooth_dinglepop_mock.reset_mock()

    # check adding several times the same task does nothing
    await Task.run([take_dinglepop // smooth_dinglepop // take_dinglepop])

    take_dinglepop_mock.assert_awaited_once()
    smooth_dinglepop_mock.assert_awaited_once()


async def test_task_tags() -> None:
    dinglepop_mock = AsyncMock()
    dinglepop = task("plumbus", "dinglepop")(dinglepop_mock)()

    schleem_mock = AsyncMock()
    schleem = task("plumbus", "schleem")(schleem_mock)()

    # check adding several times the same task does nothing
    await Task.run([dinglepop, schleem], [["dinglepop"]])

    dinglepop_mock.assert_awaited_once()
    schleem_mock.assert_not_awaited()

    dinglepop_mock.reset_mock()
    schleem_mock.reset_mock()
    await Task.run([dinglepop, schleem], [["plumbus"]])

    dinglepop_mock.assert_awaited_once()
    schleem_mock.assert_awaited_once()

    dinglepop_mock.reset_mock()
    schleem_mock.reset_mock()
    await Task.run(
        [dinglepop, schleem], [["plumbus", "dinglepop"], ["plumbus", "schleem"]]
    )

    dinglepop_mock.assert_awaited_once()
    schleem_mock.assert_awaited_once()

    dinglepop_mock.reset_mock()
    schleem_mock.reset_mock()

    await Task.run([dinglepop, schleem], [["schleem", "dinglepop"]])
    dinglepop_mock.assert_not_awaited()
    schleem_mock.assert_not_awaited()


async def test_task_scope_tags() -> None:
    dinglepop_mock = AsyncMock()
    with Task.tags("plumbus"):
        dinglepop = task()(dinglepop_mock)()

    await Task.run([dinglepop], [["plumbus"]])

    dinglepop_mock.assert_awaited_once()
    dinglepop_mock.reset_mock()

    await Task.run([dinglepop], [["schleem"]])

    dinglepop_mock.assert_not_awaited()


async def test_skip_task() -> None:
    dinglepop_mock = AsyncMock()
    dinglepop = task("dinglepop")(dinglepop_mock)

    schleem_mock = AsyncMock()
    schleem = task("schleem")(schleem_mock)

    grumbo_mock = AsyncMock()
    grumbo = task("grumbo")(grumbo_mock)

    switch_task = dinglepop() | schleem() | grumbo()

    await Task.run([switch_task])

    dinglepop_mock.assert_awaited_once()
    schleem_mock.assert_not_awaited()
    grumbo_mock.assert_not_awaited()

    dinglepop_mock.reset_mock()
    schleem_mock.reset_mock()
    grumbo_mock.reset_mock()
    await Task.run([switch_task], [["schleem"]])

    dinglepop_mock.assert_not_awaited()
    schleem_mock.assert_awaited_once()
    grumbo_mock.assert_not_awaited()

    dinglepop_mock.reset_mock()
    schleem_mock.reset_mock()
    grumbo_mock.reset_mock()
    await Task.run([switch_task], [["no-match"]])

    dinglepop_mock.assert_not_awaited()
    schleem_mock.assert_not_awaited()
    grumbo_mock.assert_not_awaited()
