"""Base types and utilities to declare an inventory."""
from asyncio import gather
from logging import Logger, getLogger
from re import compile
from typing import Awaitable, Callable, Iterable, Mapping, TypeVar

Task = Callable[["Inventory"], Awaitable[None]]

TargetType = TypeVar("TargetType", bound="Target")

TargetTask = Callable[[TargetType, "Inventory"], Awaitable[None]]

TaskMap = Mapping[str, Task]

_TASK_METHOD_FLAG = "__jshell_is_task"


def task(function: TargetTask[TargetType]) -> TargetTask[TargetType]:
    """Register a Target instance method as a task."""

    setattr(function, _TASK_METHOD_FLAG, True)
    return function


class Target:
    """Base class for an inventory target."""

    def __init__(self, name: str, tasks: Mapping[str, Task] | None = None) -> None:
        self._name = name
        self._tasks = dict(tasks or {})

    @property
    def name(self) -> str:
        return self._name

    @property
    def tasks(self) -> Mapping[str, Task]:
        return self._tasks

    @property
    def log(self) -> Logger:
        """Return a python Logger related to this host.

        The logger name will be jshell.runtime.inventory.target_name. It's
        usable to filter log messages.
        """
        return getLogger(f"jshell.targets.{self.name}")


class Inventory:
    """Collection of targets."""

    def __init__(self, targets: Iterable[Target]) -> None:
        self._targets = list(targets)

    @property
    def targets(self) -> Iterable[Target]:
        return self._targets

    @property
    def log(self) -> Logger:
        """Return a python Logger usable to report concerning the whole inventory."""
        return getLogger("jshell.inventory")

    async def run(self, task_name: str, include: list[str] | None = None) -> None:
        """Run the specified task on this inventory.

        Will run in parallell all tasks registered under the key "task_name"
        in the tasks fields of the targets of this inventory, or any method
        decorated with the @task decorator declared on Target classes.

        :param task_name: Name of the task.
        :param include: List of pattern that target names to include must match.
        """
        await gather(*self._get_tasks(task_name, include or []))

    def _get_tasks(
        self, task_name: str, include: list[str]
    ) -> Iterable[Awaitable[None]]:
        include_patterns = [compile(it) for it in include]
        for target in self._targets:
            if include_patterns and all(
                it.match(target.name) is None for it in include_patterns
            ):
                continue
            pending_task = self._get_target_task(task_name, target)
            if pending_task is not None:
                self.log.info("starting task %s.%s", target.name, task_name)
                yield pending_task

    def _get_target_task(
        self, task_name: str, target: Target
    ) -> Awaitable[None] | None:
        if task_name in target.tasks:
            return target.tasks[task_name](self)

        for method_name in dir(target):
            method: Task = getattr(target, method_name)
            if getattr(method, _TASK_METHOD_FLAG, False):
                return method(self)

        return None
