# Commands

## Overview

Jean-IaC provides an abstraction over systems allowing to launch process : [the
Shell class](../../api/shell/#jiac.shell.Shell). This allows to create process,
pipe them to other processes from others shell, redirect, record and log their
output and test for their return codes.

In a nutshell :

```python
from jiac.systems.local import LocalShell

shell = LocalShell()

await (shell("echo 'Wubba lubba'") | shell("cat > ~/wubba"))
```

Which is a very convoluted way to write "Wubba lubba" to the file ~/wubba.

## Process creation

To launch a process, first thing you need is a shell. There are several shell
implementations in Jean-IaC. (TODO: link to shell implementations). When you
call a shell with a command string, an instance of the
[Command](../../api/shell/#jiac.shell.Command) is created. The process isn't
started yet. To do so, the command must be started. There are several ways to
start a command : awaiting it, and opening it's standard input for writing.

### Awaiting a command

```python
from jiac.systems.local import LocalShell

shell = LocalShell()
command = shell("echo 'Wubba lubba'") # Nothing started yet

await command # Process is launched
# Process is terminated

```

The value returned by awaiting a command is the return code of the launched
process.

!!! note

    By default, a shell will raise a
    [FailedProcessError](../../api/shell/#jiac.shell.FailedProcessError) if a
    command returns a non-zero exit code. If you expect a process to return
    non-zero exit code and don't want an exception to be raised, check the
    section [Exit code handling](#exit-code-handling)

A command can be awaited multiple times, a new process will be created each time :

```python
from jiac.systems.local import LocalShell

shell = LocalShell()
command = shell("echo 'Wubba lubba' >> ~/wuba")

await command
await command

# ~/wubba:
# Wubba lubba
# Wubba lubba
```

### Writing to stdin

Another way to start and execute a process from a command is by opening it's
standard input for writing. This is done with an async context manager :

```python
from jiac.systems.local import LocalShell

shell = LocalShell()
command = shell("cat > ~/wuba")

async with command.write_stdin() as stdin:
    stdin.write(b"Wubba lubba")

# ~/wubba:
# Wubba lubba
```

As it is explained in the [Piping &
Redirection](../../api/shell/#jiac.shell.Command) section, this isn't the only
nor the easiest way to write something to a process stdin. But doing things
this way can be usefull if you have dynamic input to write to a command
standard input, and want to handle it in a streamed fashion.

If the command fails, by default, a
[FailedProcessError](../../api/shell/#jiac.shell.FailedProcessError) will be
raised, so you can handle failures even without getting the process exit code.


## Piping & redirection

## Environment setting

## Logging

## Exit code handling

## Built-in commands

## Custom command implementation

## Custom shell implementation
