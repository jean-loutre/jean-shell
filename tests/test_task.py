from jtoto import task, Task
from asyncio import sleep
from unittest.mock import AsyncMock
from typing import AsyncIterator, Any, Callable, Iterable
from contextlib import asynccontextmanager


def mock_task(
    tags: Iterable[str] | None = None, return_value: Any = None
) -> tuple[AsyncMock, Callable[..., Task[Any]]]:
    task_mock = AsyncMock(return_value=return_value)
    return task_mock, task(tags=tags)(task_mock)


async def test_tasks_args_dependencies() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(return_value="dinglebop")
    smooth_dinglebop_mock, smooth_dinglebop = mock_task()

    dinglebop = take_dinglebop()
    await smooth_dinglebop(dinglebop, dinglebop, "schleems").run()

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

    await smooth_dinglebop(take_dinglebop()).run()

    assert sequence == ["one", "two", "three"]


async def test_then() -> None:
    sequence = []

    @task(tags=["take"])
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

    await push_through_grumbo(
        take_dinglebop_task, take_dinglebop_task.then(smooth_dinglebop_task)
    ).run()

    assert sequence == ["one", "two"]

    sequence.clear()
    # alternative form
    await push_through_grumbo(
        take_dinglebop_task, take_dinglebop_task & smooth_dinglebop_task
    ).run()

    assert sequence == ["one", "two"]
    sequence.clear()

    await (smooth_dinglebop_task & take_dinglebop_task).run(["take"])

    # take is executed twice, because a new task is created by the & operator.
    assert sequence == ["one", "two", "one"]


async def test_join() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(return_value="dinglepop")
    smooth_dinglebop_mock, smooth_dinglebop = mock_task()
    rub_dinglebop_mock, rub_dinglebop = mock_task()

    # check adding several times the same task does nothing
    take_dinglebop_task = take_dinglebop()
    await (smooth_dinglebop().join(take_dinglebop_task).join(take_dinglebop_task)).run()

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once()

    take_dinglebop_mock.reset_mock()
    smooth_dinglebop_mock.reset_mock()
    await (
        rub_dinglebop(take_dinglebop_task // smooth_dinglebop() // take_dinglebop_task)
    ).run()

    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once()
    rub_dinglebop_mock.assert_awaited_once_with("dinglepop")


async def test_task_tags() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(tags=["plumbus", "dinglebop"])
    smooth_dinglebop_mock, smooth_dinglebop = mock_task(tags=["plumbus", "schleem"])

    async def _run(*tags: list[str]) -> None:
        take_dinglebop_mock.reset_mock()
        smooth_dinglebop_mock.reset_mock()

        await (take_dinglebop() // smooth_dinglebop()).run(*tags)

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

    await dinglebop.run(["plumbus"])

    dinglebop_mock.assert_awaited_once()
    dinglebop_mock.reset_mock()

    await dinglebop.run(["schleem"])

    dinglebop_mock.assert_not_awaited()


async def test_skip_task() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(tags=["dinglebop"])
    smooth_dinglebop_mock, smooth_dinglebop = mock_task(tags=["schleem"])
    push_dinglebop_mock, push_dinglebop = mock_task(tags=["grumbo"])

    async def _run(*tags: list[str]) -> None:
        take_dinglebop_mock.reset_mock()
        smooth_dinglebop_mock.reset_mock()
        push_dinglebop_mock.reset_mock()

        await (take_dinglebop() | smooth_dinglebop() | push_dinglebop()).run(*tags)

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


async def test_skip_child_task() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(tags=["dinglebop"])
    smooth_dinglebop_mock, smooth_dinglebop = mock_task(tags=["schleem"])
    push_dinglebop_mock, push_dinglebop = mock_task(tags=["schleem"])

    await push_dinglebop(take_dinglebop() | smooth_dinglebop()).run("schleem")

    take_dinglebop_mock.assert_not_awaited()
    smooth_dinglebop_mock.assert_awaited_once()
    push_dinglebop_mock.assert_awaited_once()


async def test_await_task() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task(
        "dinglebop", return_value="dinglebop"
    )

    assert await take_dinglebop() == "dinglebop"
