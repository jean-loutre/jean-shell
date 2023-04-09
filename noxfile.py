"""Nox configuration file"""
from typing import Callable

from nox import Session
from nox import session as nox_session


def session(
    *tags: str, python: list[str] | None = None
) -> Callable[[Callable[[Session], None]], Callable[[Session], None]]:
    return nox_session(reuse_venv=True, tags=list(tags), python=python)


# pre-commit
@session("pre-commit")
def fix_black(session: Session) -> None:
    """Fix black formatting."""
    session.install("black")
    session.run("black", ".")


@session("pre-commit")
def fix_isort(session: Session) -> None:
    """Fix imports sorting"""
    session.install("isort")
    session.run("isort", ".")


# linting
@session("lint", "checks")
def check_black(session: Session) -> None:
    """Check black formatting."""
    session.install("black")
    session.run("black", "--check", ".")


@session("lint", "checks")
def check_isort(session: Session) -> None:
    """Check imports sorting"""
    session.install("isort")
    session.run("isort", "--check", ".")


@session("lint", "checks", "pre-commit")
def flake8(session: Session) -> None:
    """Run flake8"""
    session.install("flake8")
    session.run("flake8")


@session("lint", "checks", "pre-commit")
def mypy(session: Session) -> None:
    """Run Mypy"""
    devenv(session)
    session.install("mypy")
    session.run("mypy")


# testing
@session("checks", "tests", python=["3.10"])
def unit_tests(session: Session) -> None:
    """Run unit tests."""
    devenv(session)
    session.run("python", "-m", "pytest", "--cov=jshell")


# build / publish
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


@session()
def devenv(session: Session) -> None:
    "Install development environment." ""
    session.install("-e", ".[dev]")


@session()
def publish(session: Session) -> None:
    """
    Publish a package to pypi
    """
    session.install("build", "twine")
    session.run("python", "-m", "build")
    session.run("python", "-m", "twine", "check", "dist/*")
    session.run("python", "-m", "twine", "upload", "-u", "__token__", "dist/*")
