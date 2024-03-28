from asyncio import Event, TaskGroup

from itertools import chain
from inspect import signature
from contextlib import asynccontextmanager
from functools import wraps
from inspect import isasyncgen
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Self,
    Callable,
    Generic,
    Iterable,
    TypeVar,
    cast,
    get_args,
)

T = TypeVar("T")
U = TypeVar("U")

ExecuteTask = Callable[..., Awaitable[T] | AsyncIterator[T]]
Args = Iterable[Any]
KwArgs = dict[str, Any]
TaskMiddleware = Callable[[Callable[..., Any], Args, KwArgs], tuple[Args, KwArgs]]


class Task(Generic[T]):
    def __init__(self, schedule: Callable[[TaskMiddleware], "_ScheduledTask[T]"]) -> None:
        self.__schedule = schedule

    def __getattr__(self, name: str) -> "Task[Any]":
        @Task.defer
        def get(self: Self) -> Task[Any]:
            return cast(Task[Any], getattr(self, name))

        return get(self)

    def __call__(self, *args: Any, **kwargs: Any) -> "Task[Any]":
        @Task.create
        async def call(self: T, *args: Any, **kwargs: Any) -> Any:
            return await self(*args, **kwargs)  # type: ignore

        return call(self, *args, **kwargs)

    def __floordiv__(self, other: "Task[U]") -> "Task[U]":
        @Task.create
        async def _join(_: T, other: U) -> U:
            return other

        return _join(self, other)

    @staticmethod
    async def run(tasks: Iterable["Task[Any]"], middlewares: Iterable[TaskMiddleware] | None = None) -> None:
        cache: dict[Task[Any], _ScheduledTask[Any]] = {}

        def schedule(arg: Any) -> Any:
            if not isinstance(arg, Task):
                return arg

            if arg not in cache:
                cache[arg] = arg.__schedule(all_middlewares)

            return cache[arg]

        def all_middlewares(execute: Callable[..., Any], args: Args, kwargs: KwArgs) -> tuple[Args, KwArgs]:
            for middleware in middlewares or []:
                args, kwargs = middleware(execute, args, kwargs)

            return [schedule(arg) for arg in args], {name: schedule(arg) for name, arg in kwargs.items()}

        for task in tasks:
            schedule(task)

        async with TaskGroup() as group:
            for scheduled_task in cache.values():
                group.create_task(scheduled_task.run())

    @staticmethod
    def create(execute: ExecuteTask[T]) -> Callable[..., "Task[T]"]:
        @wraps(execute)
        def wrapper(*args: Any, **kwargs: Any) -> Task[T]:
            def schedule(middleware: TaskMiddleware) -> _ScheduledTask[T]:
                nonlocal args, kwargs
                processed_args, processed_kwargs = middleware(execute, args, kwargs)
                return _ScheduledTask(execute, *processed_args, **processed_kwargs)

            return Task(schedule)

        return wrapper

    @staticmethod
    def defer(function: Callable[..., "Task[T]"]) -> "Task[T]":
        def schedule(middleware: TaskMiddleware) -> _ScheduledTask[T]:
            args, kwargs = middleware(function, [], {})
            task = function(*args, **kwargs)
            return task.__schedule(middleware)

        return Task(schedule)


task = Task.create
defer = Task.defer
run_tasks = Task.run


Inject = object()


def inject_middleware(container: dict[type, Any]) -> TaskMiddleware:
    def middleware(function: Callable[..., Any], args: Args, kwargs: KwArgs) -> tuple[Args, KwArgs]:
        function_signature = signature(function)
        for name, parameter in function_signature.parameters.items():
            annotation = parameter.annotation
            if annotation is None:
                continue

            if not hasattr(annotation, "__metadata__"):
                continue

            if all(it != Inject for it in annotation.__metadata__):
                continue

            underlying_type = get_args(annotation)[0]
            assert underlying_type in container, f"Missing provided type {underlying_type}"

            kwargs[name] = container[underlying_type]

        return args, kwargs

    return middleware


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
