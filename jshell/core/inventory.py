"""Base types and utilities to declare an inventory."""
from asyncio import gather
from typing import Awaitable, Callable, Iterable

Task = Callable[[], Awaitable[None]]


class Inventory:
    """Collection of targets."""

    def __init__(self, *targets: tuple[set[str], Task]) -> None:
        self._tasks = list(targets)

    def task(self, *tags: str) -> Callable[[Task], Task]:
        def _wrapper(func: Task) -> Task:
            tag_set = set(tags)
            tag_set.add(func.__name__)
            self._tasks.append((tag_set, func))
            return func

        return _wrapper

    async def run(self, *tags: str) -> None:
        """Run the tasks with the specified tags

        :param tags: Tags to run.
        """
        await gather(*self._get_tasks(set(tags)))

    def _get_tasks(self, tags: set[str]) -> Iterable[Awaitable[None]]:
        for task_tags, task in self._tasks:
            if task_tags & tags:
                yield task()
