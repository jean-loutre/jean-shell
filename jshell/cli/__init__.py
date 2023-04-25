"""Jean-Shell CLI wrapper."""
from typing import Callable, TypeVar

from click import argument, option

R = TypeVar("R")


def jshell_run_arguments(func: Callable[..., R]) -> Callable[..., R]:
    for it in [
        argument("operation"),
        option("-i", "--include", multiple=True, type=str),
    ]:
        func = it(func)
    return func
