#!/usr/bin/python
"""jshell setup."""
from pathlib import Path

from setuptools import find_namespace_packages, setup

setup(
    name="jshell",
    description="",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    keywords=["IT", "otters"],
    packages=find_namespace_packages(include=["jshell.*"]),
    entry_points={
        "console_scripts": [
            "jshell=jshell.cli.__main__:main",
        ]
    },
    license="WTFPL",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
    ],
    install_requires=["click", "asyncssh", "aiofile"],
    extras_require={
        "dev": [
            "nox",
            "pytest",
            "pytest-asyncio",
            "pytest-cov",
            "pytest-datadir",
            "types-click",
            "types-pyOpenSSL",
        ]
    },
    author="Jean-Loutre",
    author_email="jean-loutre@gmx.com",
    zip_safe=False,
    setuptools_git_versioning={
        "enabled": True,
    },
)
