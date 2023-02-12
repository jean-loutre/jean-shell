from jshell.core.pipe import decode, echo, stdout
from jshell.core.shell import Shell


async def set_packages(
    sh: Shell, *packages: str, sources_list: str | None = None
) -> None:
    if sources_list is not None:
        await (echo(sources_list) | sh("cat > /etc/apt/sources.list"))

    await sh("apt update")

    installed_packages = await (sh("apt-mark showmanual") | stdout() | decode())
    if installed_packages:
        installed_packages = installed_packages.replace("\n", " ")
        await sh(f"apt-mark auto {installed_packages}")

    package_list = " ".join(packages)
    with sh.env(DEBIAN_FRONTEND="noninteractive"):
        await sh(f"apt-get -yq install {package_list}")
        await sh("apt-get -yq dist-upgrade")
        await sh("apt-get -yq autoremove --purge")
