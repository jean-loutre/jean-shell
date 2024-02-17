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
    cast,
    Generator,
    Generic,
    Awaitable,
    Callable,
    TypeVar,
    AsyncContextManager,
    ParamSpec,
    Iterator,
)
from functools import wraps
from itertools import chain
from asyncio import Event, TaskGroup
from contextlib import AbstractAsyncContextManager, contextmanager


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

    _scope_tags: list[str] = []

    def __init__(
        self,
        function: "ExecuteTask[T]",
        args: list[Any],
        kwargs: dict[str, Any],
        explicit_dependencies: list["Task[Any]"] | None = None,
        tags: frozenset[str] | None = None,
        skip: "Task[T] | None" = None,
    ) -> None:
        self._function = function
        self._args = list(args)
        self._kwargs = dict(kwargs)
        self._explicit_dependencies = explicit_dependencies or []
        self._tags = tags or frozenset(Task._scope_tags)
        self._skip = skip

    def __await__(self) -> Generator[None, None, T]:
        async def _run() -> T:
            result_dict = await self._run()
            return cast(T, result_dict[self]._result)

        return _run().__await__()

    async def run(self, *tags: Iterable[str]) -> None:
        """Run the given tasks.

        Build the graph task, using the return value -> argument and explicit
        dependencies relations between tasks, and run them. If any task raises
        an exception, the whole task graph is canceled.

        Can be given an iterable of tag set, which are iterable of string
        themselves. If specified, only the tasks that have all the tags of at
        least one tag set will be selected. All the dependencies of selected
        tags will be selected.

        Args:
            tasks: An iterable of Tasks of any type.
            tags: An iterable of tag set.
        """
        await self._run(*tags)

    @staticmethod
    @contextmanager
    def tags(*tags: str) -> Iterator[None]:
        """Add tags to all tasks initialized in a scope.

        Return a context manager. All tasks created inside the context manager will
        have the given tags added as their tags. This allows defining group of
        tasks by declaring them in the scope of a context manager.

        Args:
            *tags: List of tags to apply to task declared in the scope of the
                   context manager.
        """
        old_tags = Task._scope_tags
        Task._scope_tags = old_tags + list(tags)
        yield
        Task._scope_tags = old_tags

    def then(self, task: "Task[U]") -> "Task[U]":
        """Execute given task after self.

        Return a new task, that will execute the same function and wait for the
        same dependencies as the given task, but will also wait for self to be
        finished before being started.

        This allow declaring dependencies between tasks that aren't related to
        a task's function's arguments.

        In terms of the task DAG, it adds an edge from self to task.

        You can use the & operator between self and task to achieve the same
        result.

        Args:
            task: The task to execute after self.
        """
        return Task(
            task._function,
            task._args,
            task._kwargs,
            task._explicit_dependencies + [self],
            task._tags,
        )

    def along_with(self, task: "Task[U]") -> "Task[None]":
        """Execute given task in parallel .

        Return a new task, that will execute noting, but will wait for both
        self and the given task to be finished before being started.

        This allow declaring dependencies between tasks that aren't related to
        a task's function's arguments.

        In terms of the task DAG, it adds a new noop node to the graph, and an
        edge from self to the created node, and another from task to the
        created node. If self or the given task are already noops, the task
        node will be discarded and it's dependencies directly linked to the
        newly created node.

        You can use the // operator to achieve the same result.

        Args:
            task: The task to execute along with.
        """
        explicit_dependencies = []
        for it in [self, task]:
            if isinstance(it, Noop):
                explicit_dependencies.extend(it._explicit_dependencies)
            else:
                explicit_dependencies.append(it)

        return Noop(explicit_dependencies)

    def skip_with(self, task: "Task[T]") -> "Task[T]":
        """Set the "skip task" for this task.

        If a task is a dependency of a selected task, but is not itself
        selected while running a task graph, and it has a skip tag set, the
        skip task will be executed instead of the regular function. This allow
        providing an alternate way to provide a needed value, when the full
        task is not itself wanted.

        You can use the | operator to achieve the same result.

        Args:
            task: Task to execute instead of self if self is not selected for
                  execution but it's value is needed by a selected task.

        Return:
            self, for chaining calls
        """
        if self._skip is None:
            return Task(
                self._function,
                self._args,
                self._kwargs,
                self._explicit_dependencies,
                self._tags,
                task,
            )
        return Task(
            self._function,
            self._args,
            self._kwargs,
            self._explicit_dependencies,
            self._tags,
            self._skip | task,
        )
        self._skip = task
        return self

    def __and__(self, task: "Task[U]") -> "Task[U]":
        return self.then(task)

    def __floordiv__(self, task: "Task[U]") -> "Task[None]":
        return self.along_with(task)

    def __or__(self, task: "Task[T]") -> "Task[T]":
        return self.skip_with(task)

    async def _run(
        self, *tags: Iterable[str]
    ) -> dict["Task[Any]", "_ScheduledTask[Any]"]:
        scheduled_tasks: dict[Task[Any], _ScheduledTask[Any]] = {}
        tag_sets = set(frozenset(tag_set) for tag_set in tags or [])
        self._schedule(scheduled_tasks, tag_sets)

        async with TaskGroup() as group:
            for scheduled_task in scheduled_tasks.values():
                group.create_task(scheduled_task.run())

        return scheduled_tasks

    def _schedule(
        self,
        scheduled_tasks: "dict[Task[Any], _ScheduledTask[Any]]",
        tag_sets: set[frozenset[str]],
        force: bool = False,
    ) -> "_ScheduledTask[T]":
        if self in scheduled_tasks:
            return scheduled_tasks[self]

        task_selected = len(tag_sets) == 0 or any(
            tags & self._tags == tags for tags in tag_sets
        )

        if not task_selected and self._skip is not None:
            return self._skip._schedule(scheduled_tasks, tag_sets, force)

        def _scheduled(arg: Any) -> Any:
            if isinstance(arg, Task):
                return arg._schedule(scheduled_tasks, tag_sets, task_selected or force)
            return arg

        scheduled_args = [_scheduled(it) for it in self._args]
        scheduled_kwargs = {
            key: _scheduled(value) for key, value in self._kwargs.items()
        }
        scheduled_explicit_dependencies = [
            _scheduled(dep) for dep in self._explicit_dependencies
        ]

        if not task_selected and not force:
            return None

        scheduled_task = _ScheduledTask(
            self._function,
            scheduled_args,
            scheduled_kwargs,
            scheduled_explicit_dependencies,
        )

        scheduled_tasks[self] = scheduled_task
        return scheduled_task


async def _noop() -> None:
    ...


class Noop(Task[None]):
    def __init__(self, explicit_dependencies: list["Task[Any]"] | None = None) -> None:
        super().__init__(_noop, [], {}, explicit_dependencies)


# @desc Type of function that can be wrapped in tasks.
ExecuteTask = Callable[..., Awaitable[T] | AsyncContextManager[T]]


def task(
    *tags: str,
) -> Callable[
    [Callable[..., Awaitable[T] | AsyncContextManager[T]]], Callable[..., Task[T]]
]:
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
            with Task.tags(*tags):
                return Task(func, list(args), dict(kwargs))

        return _wrapper

    return _decorate


class _ScheduledTask(Generic[T]):
    def __init__(
        self,
        function: ExecuteTask[T],
        args: list[Any],
        kwargs: dict[str, Any],
        explicit_dependencies: list["_ScheduledTask[Any]"],
    ) -> None:
        self._function = function
        self._explicit_dependencies = explicit_dependencies
        self._args = args
        self._kwargs = kwargs
        self._result: T | _Unset = _Unset()
        self._ready = Event()
        self._done = Event()
        self._dependent_tasks_done: list[Event] = []

        for arg in chain(args, kwargs.values()):
            if isinstance(arg, _ScheduledTask):
                arg._dependent_tasks_done.append(self._done)

    async def run(self) -> None:
        async with TaskGroup() as group:
            for explicit_dependency in self._explicit_dependencies:
                group.create_task(explicit_dependency._wait_result())

        async def _load_arg(arg: Any) -> Any:
            if isinstance(arg, _ScheduledTask):
                return await arg._wait_result()
            return arg

        args = list([await _load_arg(arg) for arg in self._args])
        kwargs = {key: await _load_arg(arg) for key, arg in self._kwargs.items()}

        task_return = self._function(*args, **kwargs)

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
