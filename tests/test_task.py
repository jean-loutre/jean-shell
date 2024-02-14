from jiac import task, Task
from asyncio import sleep
from unittest.mock import AsyncMock
from typing import AsyncIterator, Any, Callable
from contextlib import asynccontextmanager


def mock_task(
    *tags: str, return_value: Any = None
) -> tuple[AsyncMock, Callable[..., Task[Any]]]:
    task_mock = AsyncMock(return_value=return_value)
    return task_mock, task(*tags)(task_mock)


async def test_tasks_args_dependencies() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(return_value="dinglebop")
    smooth_dinglebop_mock, smooth_dinglebop = mock_task()

    dinglebop = take_dinglebop()
    await Task.run([smooth_dinglebop(dinglebop, dinglebop, "schleems")])

    # Should've been awaited only once
    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once_with("dinglebop", "dinglebop", "schleems")


async def test_async_context_manager_task() -> None:
    sequence = []

    @task()
    @asynccontextmanager
    async def take_dinglebop() -> AsyncIterator[str]:
        sequence.append("one")
        yield "dinglebop"
        sequence.append("three")

    @task()
    async def smooth_dinglebop(dinglebop: str) -> None:
        assert dinglebop == "dinglebop"
        sequence.append("two")

    await Task.run([smooth_dinglebop(take_dinglebop())])

    assert sequence == ["one", "two", "three"]


async def test_then() -> None:
    sequence = []

    @task()
    async def take_dinglebop() -> None:
        await sleep(0.1)
        sequence.append("one")

    @task()
    async def smooth_dinglebop(dinglebop: str) -> str:
        sequence.append("two")
        return "smoothed dinglebop"

    @task()
    async def push_through_grumbo(base_dinglebop: str, smoothed_dinglebop: str) -> None:
        assert smoothed_dinglebop == "smoothed dinglebop"

    take_dinglebop_task = take_dinglebop()
    smooth_dinglebop_task = smooth_dinglebop(take_dinglebop_task)

    await Task.run(
        [
            push_through_grumbo(
                take_dinglebop_task, take_dinglebop_task.then(smooth_dinglebop_task)
            )
        ]
    )

    assert sequence == ["one", "two"]

    sequence.clear()
    # alternative form
    await Task.run(
        [
            push_through_grumbo(
                take_dinglebop_task, take_dinglebop_task & smooth_dinglebop_task
            )
        ]
    )

    assert sequence == ["one", "two"]


async def test_along_with() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task()
    smooth_dinglebop_mock, smooth_dinglebop = mock_task()

    # check adding several times the same task does nothing
    take_dinglebop_task = take_dinglebop()
    await Task.run(
        [
            smooth_dinglebop()
            .along_with(take_dinglebop_task)
            .along_with(take_dinglebop_task)
        ]
    )

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once()

    take_dinglebop_mock.reset_mock()
    smooth_dinglebop_mock.reset_mock()
    await Task.run([take_dinglebop_task // smooth_dinglebop() // take_dinglebop_task])

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once()


async def test_task_tags() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task("plumbus", "dinglebop")
    smooth_dinglebop_mock, smooth_dinglebop = mock_task("plumbus", "schleem")

    async def _run(*tags: list[str]) -> None:
        take_dinglebop_mock.reset_mock()
        smooth_dinglebop_mock.reset_mock()

        await Task.run([take_dinglebop(), smooth_dinglebop()], list(tags))

    await _run(["dinglebop"])

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_not_awaited()

    await _run(["plumbus"])

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once()

    await _run(["plumbus", "dinglebop"], ["plumbus", "schleem"])

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once()

    await _run(["schleem", "dinglebop"])

    take_dinglebop_mock.assert_not_awaited()
    smooth_dinglebop_mock.assert_not_awaited()


async def test_task_scope_tags() -> None:
    dinglebop_mock = AsyncMock()
    with Task.tags("plumbus"):
        dinglebop = task()(dinglebop_mock)()

    await Task.run([dinglebop], [["plumbus"]])

    dinglebop_mock.assert_awaited_once()
    dinglebop_mock.reset_mock()

    await Task.run([dinglebop], [["schleem"]])

    dinglebop_mock.assert_not_awaited()


async def test_skip_task() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task("dinglebop")
    smooth_dinglebop_mock, smooth_dinglebop = mock_task("schleem")
    push_dinglebop_mock, push_dinglebop = mock_task("grumbo")

    async def _run(*tags: list[str]) -> None:
        take_dinglebop_mock.reset_mock()
        smooth_dinglebop_mock.reset_mock()
        push_dinglebop_mock.reset_mock()

        await Task.run(
            [take_dinglebop() | smooth_dinglebop() | push_dinglebop()], list(tags)
        )

    await _run()

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_not_awaited()
    push_dinglebop_mock.assert_not_awaited()

    await _run(["schleem"])

    take_dinglebop_mock.assert_not_awaited()
    smooth_dinglebop_mock.assert_awaited_once()
    push_dinglebop_mock.assert_not_awaited()

    await _run(["no-match"])

    take_dinglebop_mock.assert_not_awaited()
    smooth_dinglebop_mock.assert_not_awaited()
    push_dinglebop_mock.assert_not_awaited()
