from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from functools import wraps
from inspect import Signature, isasyncgen, signature
from itertools import chain
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Generic,
    Iterable,
    TypeVar,
    cast,
    get_args,
)

T = TypeVar("T")
U = TypeVar("U")

ExecuteTask = Callable[..., Awaitable[T] | AsyncIterator[T]]

Inject = object()


class Task(Generic[T]):
    def __init__(self, schedule: Callable[["_Scheduler"], "_ScheduledTask[T]"]) -> None:
        self.__schedule = schedule

    def __getattr__(self, name: str) -> "Task[Any]":
        @self.from_function
        async def get(self: T) -> Any:
            return getattr(self, name)

        return get(self)

    def __call__(self, *args: Any, **kwargs: Any) -> "Task[Any]":
        @self.from_function
        async def call(self: T, *args: Any, **kwargs: Any) -> Any:
            return await self(*args, **kwargs)  # type: ignore

        return call(self, *args, **kwargs)

    def __floordiv__(self, other: "Task[U]") -> "Task[U]":
        @Task.from_function
        async def _join(_: T, other: U) -> U:
            return other

        return _join(self, other)

    def schedule(self, scheduler: "_Scheduler") -> "_ScheduledTask[T]":
        return scheduler.get_scheduled_task(self, self.__schedule)

    @staticmethod
    def from_function(execute: ExecuteTask[T]) -> Callable[..., "Task[T]"]:
        @wraps(execute)
        def wrapper(*args: Any, **kwargs: Any) -> Task[T]:
            def schedule(scheduler: _Scheduler) -> _ScheduledTask[T]:
                def schedule_arg(arg: Any) -> Any:
                    if isinstance(arg, Task):
                        return arg.schedule(scheduler)
                    return arg

                all_kwargs = scheduler.get_injected_args(signature(execute)) | dict(kwargs)

                return _ScheduledTask(
                    execute,
                    *[schedule_arg(arg) for arg in args],
                    **{name: schedule_arg(arg) for name, arg in all_kwargs.items()},
                )

            return Task(schedule)

        return wrapper

    @staticmethod
    def from_schedule_function(function: Callable[..., "Task[T]"]) -> "Task[T]":
        def schedule(scheduler: _Scheduler) -> _ScheduledTask[T]:
            kwargs = scheduler.get_injected_args(signature(function))
            task = function(**kwargs)
            return task.schedule(scheduler)

        return Task(schedule)

    def __await__(self) -> Generator[None, None, T]:
        return self.__schedule(_Scheduler({})).run().__await__()


task = Task.from_function
schedule = Task.from_schedule_function


class _Unset:
    ...


class _ScheduledTask(Generic[T]):
    def __init__(self, execute: ExecuteTask[T], *args: Any, **kwargs: Any) -> None:
        self.__execute = execute
        self.__args = list(args)
        self.__kwargs = dict(kwargs)
        self.__ready = Event()
        self.__result: T | _Unset = _Unset()
        self.__done = Event()
        self.__child_tasks_done: set[Event] = set()

        for arg in chain(self.__args, self.__kwargs.values()):
            if isinstance(arg, _ScheduledTask):
                arg.__child_tasks_done.add(self.__done)

    async def run(self) -> T:
        args = [await self.__wait_arg(arg) for arg in self.__args]
        kwargs = {name: await self.__wait_arg(arg) for name, arg in self.__kwargs.items()}

        async with self.__wrap_execute(*args, **kwargs) as self.__result:
            self.__ready.set()

            for child_task_done in self.__child_tasks_done:
                await child_task_done.wait()

            self.__done.set()
            return self.__result

    @asynccontextmanager
    async def __wrap_execute(self, *args: Any, **kwargs: Any) -> AsyncIterator[T]:
        result = self.__execute(*args, **kwargs)
        if isasyncgen(result):
            async for it in cast(AsyncIterator[T], result):
                yield it
        else:
            yield await cast(Awaitable[T], result)

    @staticmethod
    async def __wait_arg(arg: Any) -> Any:
        if isinstance(arg, _ScheduledTask):
            await arg.__ready.wait()
            assert not isinstance(arg.__result, _Unset)
            return arg.__result

        return arg


class _Scheduler:
    def __init__(self, provide: dict[type, Any]) -> None:
        self.__provide = provide
        self.__scheduled_tasks: dict[Task[Any], _ScheduledTask[Any]] = {}

    @staticmethod
    async def run(tasks: Iterable[Task[Any]], provide: Iterable[tuple[type, Any]] | None = None) -> None:
        scheduler = _Scheduler({type_: value for type_, value in (provide or [])})
        for task in tasks:
            task.schedule(scheduler)

        async with TaskGroup() as group:
            # Set is important: due to the schedule decorator, two tasks can
            # yield the same scheduled tasks, so don't execute them twice here.
            for scheduled_task in set(scheduler.__scheduled_tasks.values()):
                group.create_task(scheduled_task.run())

    def get_injected_args(self, function: Signature) -> dict[str, Any]:
        injected_args = {}
        for name, parameter in function.parameters.items():
            annotation = parameter.annotation
            if annotation is None:
                continue

            if not hasattr(annotation, "__metadata__"):
                continue

            if all(it != Inject for it in annotation.__metadata__):
                continue

            underlying_type = get_args(annotation)[0]
            assert underlying_type in self.__provide, f"Missing provided type {underlying_type}"

            injected_args[name] = self.__provide[underlying_type]

        return injected_args

    def get_scheduled_task(
        self, task: Task[T], create_scheduled_task: Callable[["_Scheduler"], _ScheduledTask[T]]
    ) -> _ScheduledTask[T]:
        if task not in self.__scheduled_tasks:
            self.__scheduled_tasks[task] = create_scheduled_task(self)

        return self.__scheduled_tasks[task]


run_tasks = _Scheduler.run
