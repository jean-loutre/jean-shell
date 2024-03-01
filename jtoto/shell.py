"""
Process execution abstraction layer.

This module declares base classes providing a common interface to run processes
on several targets (local shell, via ssh). The api provides a shell-like syntax
allowing to execute process and redirect, read or pipe processes stdin, stdout
and stderr :

```python
 #  installs the packages installed on a remote machine locally, and writes
 #  them to the file ~/remote-packages.

 await (ssh_shell("apt list --installed") | local_shell("xargs apt install"))
 await (ssh_shell("apt-list --installed") >> FileStream("~/remote-packages"))
```
"""
from abc import ABC, abstractmethod
from asyncio import gather
from collections import deque
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
from logging import Logger, addLevelName, INFO, DEBUG
from typing import (
    overload,
    Awaitable,
    Callable,
    AsyncContextManager,
    AsyncIterator,
    Concatenate,
    Final,
    Generator,
    Iterable,
    Iterator,
    ParamSpec,
)

from jtoto.stream import (
    LineStream,
    LogStream,
    Stream,
    Streamable,
    MemoryStream,
    multiplex,
    stream_to,
    InputStream,
    copy_stream,
)

Stdin = Stream | None
Stdout = Stream | None
Stderr = Stream | None
Process = tuple[Stdout, Stderr, Awaitable[int]]
StartProcess = Callable[[Stdin, Stderr], Awaitable[Process]]


class LogLevel:
    STDERR = INFO + 1
    STDOUT = INFO - 1
    TRACE = DEBUG - 1


addLevelName(LogLevel.STDERR, "STDERR")
addLevelName(LogLevel.STDOUT, "STDOUT")
addLevelName(LogLevel.TRACE, "TRACE")


class Command:
    """A not-yet executed command.

    This class isn't indended to be constructed directly, but get as the result
    of functions decorated by the jtoto.command decorator, or returned by
    jtoto.Shell implementations.

    This is a factory of jtoto.shell.Process : each time a command is awaited,
    it starts a new process. It can also be pipe in a command or an existing
    jtoto.shell.Pipe, to create a jtoto.Pipe.

    Supports redirection to a jtoto.Stream through >> operator, which will
    redirect the standard output of the command to the given stream :
    """

    def __init__(self, start: StartProcess, logger: Logger | None = None) -> None:
        self._start = start
        self._out: Stdout = None
        self._logger = logger

    def __await__(self) -> Generator[None, None, int]:
        return Pipe([self]).__await__()

    def __or__(self, right: "Command") -> "Pipe":
        return Pipe([self, right])

    def __rshift__(self, target: "Streamable") -> "Command":
        result = Command(self._start, self._logger)
        result._out = multiplex(self._out, stream_to(target))
        return result

    def write_stdin(self) -> AsyncContextManager[Stdin]:
        return Pipe([self]).write_stdin()

    @overload
    async def read_stdout(self, encoding: None = None) -> bytes:
        ...

    @overload
    async def read_stdout(self, encoding: str) -> str:
        ...

    async def read_stdout(self, encoding: str | None = None) -> str | bytes:
        return await Pipe([self]).read_stdout(encoding)

    async def start(self, out: Stdout, err: Stderr) -> Process:
        out = multiplex(out, self._out)
        return await self._start(out, err)


P = ParamSpec("P")


def command(
    func: Callable[Concatenate[Stdout, Stderr, P], Awaitable[Process]],
) -> Callable[P, Command]:
    """Decorator to create a command for a function.

    Expect an async callable accepting two ```Stream | None``` as first
    arguments, representing the standard output and the stdandard error of the
    command, plus any user-defined arguments. The given callable should be
    async and return a tuple ```Stream | None, Stream | None, Awaitable[int]```
    corresponding to the standard input of the command, the standard error, and
    the awaitable to wait for for the command to terminate.

    Refer to the reference or to simple built-in implementations like
    ```echo``` or ```cat``` to see some examples.

    args:
        * func: Callable[[Stdout, Stderr, ...]]

    Returns:
        A callable taking user-defined arguments as parameter, and returning a Command.
    """

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> Command:
        async def _start(out: Stdout, err: Stderr) -> Process:
            return await func(out, err, *args, **kwargs)

        return Command(_start)

    return _wrapper


class Pipe:
    """A pipe of jtoto.Command ready to be executed.

    This class isn't indended to be constructed directly, but is the result of
    piping jtoto.Commands together through the use of the | operator.

    Pipes can be piped together to be combined, and awaited to be executed. The
    result of awaiting a pipe is the return code of the last command of the
    pipe.
    """

    def __init__(self, commands: list[Command]) -> None:
        self._commands = commands

    def __or__(self, right: "Pipe | Command") -> "Pipe":
        if isinstance(right, Pipe):
            return Pipe(self._commands + right._commands)
        return Pipe(self._commands + [right])

    def __await__(self) -> Generator[None, None, int]:
        async def _run() -> int:
            _, wait = await self._start()
            return await wait

        return _run().__await__()

    @asynccontextmanager
    async def write_stdin(self) -> AsyncIterator[Stdin]:
        stdin, wait = await self._start()
        try:
            yield stdin
        finally:
            if stdin:
                await stdin.close()
            await wait

    @overload
    async def read_stdout(self, encoding: None = None) -> bytes:
        ...

    @overload
    async def read_stdout(self, encoding: str) -> str:
        ...

    async def read_stdout(self, encoding: str | None = None) -> str | bytes:
        out = MemoryStream()
        _, wait = await self._start(out)
        await wait

        if encoding is None:
            return out.buffer
        return out.buffer.decode(encoding)

    async def _start(self, out: Stream | None = None) -> tuple[Stdin, Awaitable[int]]:
        err = None
        processes = []
        for command in reversed(self._commands):
            out, err, process = await command.start(out, err)
            processes.append(process)

        async def _run() -> int:
            results = await gather(*processes)
            return results[-1]

        return out, _run()


class ProcessFailedError(Exception):
    """Exception raised when a command returns a non-zero exit code.

    This exception is raised if raise_on_error is setted on the shell that
    created the command. It contains the command that failed, the return code
    of the process and the last line of stderr that were output by the process.
    """

    def __init__(self, command: str, return_code: int, stderr_tail: str) -> None:
        super().__init__(
            f"{command} returned code {return_code}.\nLast stderr output:\n{stderr_tail}"
        )
        self._command = command
        self._return_code = return_code
        self._stderr_tail = stderr_tail

    @property
    def command(self) -> str:
        """The command that failed."""
        return self._command

    @property
    def return_code(self) -> int:
        """Return code of the process that failed."""
        return self._return_code

    @property
    def stderr_tail(self) -> str:
        """Last 10 lines that were output on stderr by the process."""
        return self._stderr_tail


class _TailStream(LineStream):
    def __init__(self) -> None:
        super().__init__()
        self._tail: deque[str] = deque(maxlen=10)

    @property
    def tail(self) -> Iterable[str]:
        return self._tail

    async def write_line(self, line: str) -> None:
        self._tail.append(line)


@command
async def _raise_on_error(
    out: Stdout, err: Stderr, start: StartProcess, command_string: str
) -> Process:
    stderr_tail = _TailStream()
    err = multiplex(err, stderr_tail)
    in_, err, run = await start(out, err)

    async def _run_watch() -> int:
        result = await run

        await stderr_tail.close()

        if result != 0:
            raise ProcessFailedError(
                command_string, result, "\n".join(stderr_tail.tail)
            )

        return result

    return in_, err, _run_watch()


class Shell(ABC):
    """Abstraction of process launching system.

    This is implemented by anything that can run commands : ssh, local shell,
    nested sudo shell...

    Shells can be called with a string command, returning an instance of
    jtoto.Command that can either be piped to another command, or awaited to
    execute it.
    """

    def __init__(
        self, logger: Logger | None = None, raise_on_error: bool = True
    ) -> None:
        """Initialize the shell.

        Args:
            logger:
                The commands executed by this shell will be logged to this
                logger, as well as stdout and stderr. The shell module defines
                two logging levels in addition to python standard ones : Stdout
                will be logged on the given logger with the LogLevel.STDOUT
                level, stderr with LogLevel.STDERR.

                This argument can be overriden locally by the jtoto.Shell.log
                context manager.

            raise_on_error:
                If true, any command started by this shell that fails will
                raise a ProcessFailedError.

                This parameter can be locally overriden by using
                jtoto.Shell.raise_on_error context manager, or by setting the
                raise_on_error parameter when calling this shell to create a
                command.
        """
        self._logger = logger
        self._env: dict[str, str] = {}
        self._raise_on_error = raise_on_error

    def __call__(self, command: str, raise_on_error: bool | None = None) -> Command:
        """Create a new command ready to be executed.

        Args:
            command: The command to execute with this shell.

            raise_on_error:
                Override the raise_on_error setting set on this shell for this
                command.

        Returns:
            A jtoto.Command instance ready to be executed by awaiting it, or to
            be piped to other commands, to create a jtoto.Pipe.
        """

        async def _start(out: Stdout, err: Stderr) -> Process:
            if self._logger:
                self._logger.debug("Executing %s", command)
                if out is None and self._logger is not None:
                    out = LogStream(self._logger, level=LogLevel.STDOUT)
                if (
                    err is None or isinstance(err, _TailStream)
                ) and self._logger is not None:
                    err = multiplex(err, LogStream(self._logger, level=LogLevel.STDERR))

            return await self._start_process(out, err, command, env=self._env)

        if (raise_on_error is None and self._raise_on_error) or raise_on_error:
            result = _raise_on_error(_start, command)
        else:
            result = Command(_start)

        return result

    @contextmanager
    def env(self, **kwargs: str) -> Iterator[None]:
        """Add given keys to the environment in a scope.

        Args:
            **kwargs: key=value pairs of environment variables to set.

        Returns:
            A context manager. In the scope of this context manager, any
            command created by this shell will have the given environment, plus
            the one defined in the outer scope.
        """
        old_env = self._env.copy()
        for key, value in dict(**kwargs).items():
            self._env[key] = value
        yield
        self._env = old_env

    @contextmanager
    def log(self, logger: Logger | None) -> Iterator[None]:
        """Override the shell logger in a scope.

        Args:
            logger: logging.Logger to set as this shell's logger in the scope.

        Returns:
            A context manager. In the scope of this context manager, any
            command created by this shell will log to the given logger, instead
            of the one eventually passed in the constructor.
        """
        old_logger = self._logger
        self._logger = logger
        yield
        self._logger = old_logger

    @contextmanager
    def raise_on_error(self, raise_on_error: bool) -> Iterator[None]:
        """Override the shell raise_on_error parameter in a scope.

        Args:
            raise_on_error:
                Weither to raise ProcessFailedExecption if a command created by
                this Shell fails, in the scope of the context manager.

        Returns:
            A context manager. In the scope of this context manager, any
            command created by this shell will by default use the given value
            for it's raise_on_error parameter. Note that this can be overriden
            per-command when calling the Shell.
        """
        old_value = self._raise_on_error
        self._raise_on_error = raise_on_error
        yield
        self._raise_on_error = old_value

    @abstractmethod
    async def _start_process(
        self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
    ) -> Process:
        ...


class Redirect:
    pass


FROM_STDOUT: Final[Redirect] = Redirect()
FROM_STDERR: Final[Redirect] = Redirect()
NULL: Final[Redirect] = Redirect()


async def _return_0() -> int:
    return 0


@command
async def redirect(
    out: Stdout,
    err: Stderr,
    stdout: Redirect = FROM_STDOUT,
    stderr: Redirect = FROM_STDERR,
) -> Process:
    """Redirect standard streams.

    Args:
        stdout:
            Where to redirect pipe's previous command's standard output.

        stderr:
            Where to redirect pipe's previous command's standard output.

    Returns:
        A command that, if piped to other commands, will apply the configured
        redirections.
    """
    if stdout == FROM_STDOUT and stderr == FROM_STDOUT:
        return (multiplex(out, err), None, _return_0())
    if stdout == FROM_STDERR and stderr == FROM_STDERR:
        return (None, multiplex(out, err), _return_0())
    if stdout == FROM_STDERR and stderr == FROM_STDOUT:
        return err, out, _return_0()
    if stdout == NULL:
        return None, err, _return_0()
    if stderr == NULL:
        return out, None, _return_0()

    return out, err, _return_0()


@command
async def echo(
    out: Stdout,
    err: Stderr,
    content: bytes | str,
    encoding: str = "utf-8",
) -> Process:
    """Write a string or bytes to standard output.

    Args:
        content:
            Bytes or string to write on stdout.

        encoding:
            String encoding, if content is a string.

    Returns:
        A command that, will forward the standard output of the previous
        command in the pipe, and write given content to it's standard output.
    """

    async def _run() -> int:
        if isinstance(content, str):
            byte_content = content.encode(encoding)
        else:
            byte_content = content

        if out is not None:
            await out.write(byte_content)

        if out:
            await out.close()

        return 0

    return out, err, _run()


@command
async def cat(
    out: Stdout,
    err: Stderr,
    stream: AsyncContextManager[InputStream],
) -> Process:
    """Write a stream to standard output.

    Args:
        stream: A jtoto.InputStream to write to stdout.

    Returns:
        A command that, will forward the standard output of the previous
        command in the pipe, and write given stream to it's standard output.
    """

    async def _run() -> int:
        if out is not None:
            async with stream as in_:
                await copy_stream(in_, out)
                await out.close()

        return 0

    return out, err, _run()
