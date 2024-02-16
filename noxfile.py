"""Nox configuration file"""
from typing import Callable

from nox import Session
from nox import session as nox_session


def session(
    *tags: str, python: list[str] | None = None
) -> Callable[[Callable[[Session], None]], Callable[[Session], None]]:
    return nox_session(reuse_venv=True, tags=list(tags), python=python)


@session()
def fix_lint(session: Session) -> None:
    """Fix code linting"""
    session.install("ruff")
    session.run("ruff", "check", "--unsafe-fixes", "--fix", ".")
    session.run("ruff", "format")


@session("lint", "checks")
def ruff(session: Session) -> None:
    """Lint code"""
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format")


@session("lint", "checks", "pre-commit")
def mypy(session: Session) -> None:
    """Run Mypy"""
    devenv(session)
    session.install("mypy", "types-click", "types-pyOpenSSL")
    session.run("mypy")


@session("checks", "tests", python=["3.10", "3.11"])
def unit_tests(session: Session) -> None:
    """Run unit tests."""
    devenv(session)
    session.run("python", "-m", "pytest", "--cov=jtoto", "--cov-report=html")


@session()
def devenv(session: Session) -> None:
    "Install development environment." ""
    session.install("-e", ".[dev]")


@session()
def docs(session: Session) -> None:
    """Build documentation."""
    session.install(
        "mkdocs",
        "mkdocs-awesome-pages-plugin",
        "mkdocs-gen-files",
        "mkdocs-literate-nav",
        "mkdocs-material",
        "mkdocs-section-index",
        "mkdocstrings[python]",
    )
    session.run("mkdocs", "build")
