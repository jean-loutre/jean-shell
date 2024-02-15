# Tasks

Jean-IaC provide a way to declare directed acyclic graph of tasks.

```
@task
async def install(shell: Shell, package: str) -> None:
    await shell("apt install {package}")


task = install(shell, package)
```

## Implicit dependencies

## Explicit dependencies

## Filtering

## Skipping
