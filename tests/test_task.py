from typing import Any, AsyncIterator, Callable, Annotated
from unittest.mock import AsyncMock

from jtoto import Task, task, run_tasks, Inject


def mock_task(
    return_value: Any = None,
) -> tuple[AsyncMock, Callable[..., Task[Any]]]:
    task_mock = AsyncMock(return_value=return_value)
    return task_mock, task(task_mock)


async def test_tasks_args_dependencies() -> None:
    take_dinglebop_mock, take_dinglebop = mock_task("dinglebop")
    smooth_dinglebop_mock, smooth_dinglebop = mock_task()

    dinglebop = take_dinglebop()
    await run_tasks([smooth_dinglebop(dinglebop, dinglebop, "schleems")])

    # Should've been awaited only once
    take_dinglebop_mock.assert_awaited_once()
    smooth_dinglebop_mock.assert_awaited_once_with("dinglebop", "dinglebop", "schleems")


async def test_async_context_manager_task() -> None:
    sequence = []

    @task
    async def take_dinglebop() -> AsyncIterator[str]:
        sequence.append("one")
        yield "dinglebop"
        sequence.append("three")

    @task
    async def smooth_dinglebop(dinglebop: str) -> None:
        assert dinglebop == "dinglebop"
        sequence.append("two")

    await run_tasks([smooth_dinglebop(take_dinglebop())])

    assert sequence == ["one", "two", "three"]


async def test_task_inject() -> None:
    @task
    async def take_dinglebop(schleem: Annotated[str, Inject]) -> None:
        assert schleem == "schleem"

    await run_tasks([take_dinglebop()], provide=[(str, "schleem")])
