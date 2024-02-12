"""Task

Declare a decorator "task", that can be used to create a directed acyclic graph
of tasks, based on arguments given to the decorated function. Parameter of a
task will be executed before the function needing them. If an async context
manager is decorated by task, it will exit only when all tasks that were given
the manager's yielded value are finished. The graph can be run using the method
Task.run(...), giving it leaf tasks to execute.
"""
from typing import (
    Any,
    Iterable,
    Generic,
    Coroutine,
    Awaitable,
    Callable,
    TypeVar,
    AsyncContextManager,
    ParamSpec,
)
from functools import wraps
from itertools import chain
from asyncio import Event, TaskGroup
from contextlib import AbstractAsyncContextManager


T = TypeVar("T", covariant=True)
U = TypeVar("U", covariant=True)
P = ParamSpec("P")


class _Unset:
    ...


class Task(Generic[T]):
    """A task returning a value of type T.

    Do not instantiate directly. If you need to create a task for a function
    you can't decorate yourself, either create a wrapper, or call the task
    decorator to create a task function :

    ```python
        from third_library import fetch_url

        fetch_task = task()(fetch_url)("https://wubba-lubba.com", headers={})
    ```
    """

    def __init__(
        self,
        execute: "ExecuteTask[T]",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._closure = _Closure(execute, *args, **kwargs)
        self._result: T | _Unset = _Unset()
        self._ready = Event()
        self._done = Event()
        self._dependent_tasks_done: set[Event] = set()

    @staticmethod
    async def run(tasks: Iterable["Task[Any]"]) -> None:
        """Run the given tasks.

        Build the graph task, using the return value -> argument relation
        between tasks, and run them. If any task raises an exception, the whole
        task graph is canceled.

        Args:
            tasks: An iterable of Tasks of any type.
        """
        scheduled_tasks: set[Task[Any]] = set()
        tasks_coroutines = chain.from_iterable(
            task._schedule(
                scheduled_tasks,
            )
            for task in tasks
        )

        async with TaskGroup() as group:
            for task_coroutine in tasks_coroutines:
                group.create_task(task_coroutine)

    def _schedule(
        self, scheduled_tasks: set["Task[Any]"]
    ) -> Iterable[Coroutine[Any, Any, None]]:
        if self in scheduled_tasks:
            return

        yield self._run(self._closure)
        scheduled_tasks.add(self)

        for task in self._closure.dependencies:
            task._dependent_tasks_done.add(self._done)
            yield from task._schedule(scheduled_tasks)

    async def _run(self, callback: "_Closure[T]") -> None:
        task_return = await callback.start()

        if isinstance(task_return, AbstractAsyncContextManager):
            self._result = await task_return.__aenter__()
        else:
            self._result = await task_return

        self._ready.set()

        async with TaskGroup() as group:
            for event in self._dependent_tasks_done:
                group.create_task(event.wait())

        if isinstance(task_return, AbstractAsyncContextManager):
            await task_return.__aexit__(None, None, None)

        self._done.set()

    async def _wait_result(self) -> T:
        await self._ready.wait()
        assert not isinstance(self._result, _Unset)
        return self._result


# @desc Type of function that can be wrapped in tasks.
ExecuteTask = Callable[..., Awaitable[T] | AsyncContextManager[T]]


def task() -> (
    Callable[
        [Callable[..., Awaitable[T] | AsyncContextManager[T]]], Callable[..., Task[T]]
    ]
):
    """Transform an async function into a task factory.

    Decorate a function so that for each argument, the decorator accepts
    either T or Task[T], where T is the argument's type. If a task is
    passed as an argument of the resulting function, when task is executed
    in a task graph, the result value of the given task will be waited, and
    passed to the decorated function.

    If the decorated function returns an Awaitable, it will be regulary
    awaited. If it returns an AbstractAsyncContextManager, the context will
    remain open until all dependent tasks are done, ensuring that the
    returned value is still valid when child tasks depending on it are
    executed.
    """

    def _decorate(func: "ExecuteTask[T]") -> Callable[..., Task[T]]:
        @wraps(func)
        def _wrapper(*args: Any, **kwargs: Any) -> Task[T]:
            return Task(func, *args, **kwargs)

        return _wrapper

    return _decorate


class _Closure(Generic[T]):
    def __init__(
        self,
        function: ExecuteTask[T],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._function = function
        self._args = list(args)
        self._kwargs = dict(kwargs)

    @property
    def dependencies(self) -> Iterable["Task[Any]"]:
        for arg in chain(self._args, self._kwargs.values()):
            if isinstance(arg, Task):
                yield arg

    async def start(self) -> Awaitable[T] | AsyncContextManager[T]:
        async def _load_arg(arg: Any) -> Any:
            if isinstance(arg, Task):
                return await arg._wait_result()
            return arg

        args = list([await _load_arg(arg) for arg in self._args])
        kwargs = {key: await _load_arg(arg) for key, arg in self._kwargs.items()}

        return self._function(*args, **kwargs)