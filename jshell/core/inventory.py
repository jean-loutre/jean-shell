"""Base types and utilities to declare an inventory."""
from asyncio import gather
from dataclasses import dataclass, field
from logging import Logger, getLogger
from typing import Awaitable, Callable, Iterable, Mapping, TypeVar

Task = Callable[["Inventory"], Awaitable[None]]

TargetType = TypeVar("TargetType", bound="Target")

TargetTask = Callable[[TargetType, "Inventory"], Awaitable[None]]

TaskMap = Mapping[str, Task]

_TASK_METHOD_FLAG = "__jshell_is_task"


def task(function: TargetTask[TargetType]) -> TargetTask[TargetType]:
    """Register a Target instance method as a task.

    :param function: Function to decorate.
    :return:         Function, flagged as being a task.
    """

    setattr(function, _TASK_METHOD_FLAG, True)
    return function


@dataclass(kw_only=True, frozen=True)
class Target:
    """Base class for an inventory target."""

    # Unique name of the target.
    name: str

    # Tasks declared on this target.
    tasks: Mapping[str, Task] = field(default_factory=dict)

    @property
    def log(self) -> Logger:
        """Return a python Logger related to this host.

        The logger name will be jshell.runtime.inventory.target_name. It's
        usable to filter log messages.

        :return: A Logger instance.
        """
        return getLogger(f"jshell.runtime.inventory.{self.name}")


@dataclass(frozen=True)
class Inventory:
    """Collection of targets."""

    targets: Iterable[Target]

    @property
    def log(self) -> Logger:
        """Return a python Logger usable to report concerning the whole inventory.

        :return: A Logger instance.
        """
        return getLogger("jshell.runtime.inventory")

    async def run(self, task_name: str) -> None:
        """Run the specified task on this inventory.

        Will run in parallell all tasks registered under the key "task_name"
        in the tasks fields of the targets of this inventory, or any method
        decorated with the @task decorator declared on Target classes.

        :param task_name: Name of the task.
        """
        await gather(*self._get_tasks(task_name))

    def _get_tasks(self, task_name: str) -> Iterable[Awaitable[None]]:
        for target in self.targets:
            pending_task = self._get_target_task(task_name, target)
            if pending_task is not None:
                self.log.info("Pushing %s task for %s", task_name, target.name)
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
