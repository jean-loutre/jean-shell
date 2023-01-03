from jshell.command import echo
from jshell.shells import Shell


async def set_packages(
    shell: Shell, *packages: str, source_list: str | None = None
) -> None:
    if source_list is not None:
        await (echo(source_list) | shell.run("cat > /etc/apt/sources.list"))

    installed_packages = str(await shell.run("apt-mark showmanual"))
    if installed_packages:
        installed_packages = installed_packages.replace("\n", " ")
        await shell.run(f"apt-mark auto {installed_packages}")

    package_list = " ".join(packages)
    with shell.env(DEBIAN_FRONTEND="noninteractive"):
        await shell.run(f"apt-get -yq install {package_list}")
        await shell.run("apt-get -yq dist-upgrade")
        await shell.run("apt-get -yq autoremove --purge")
