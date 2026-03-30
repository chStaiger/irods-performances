import subprocess
import json
from getpass import getpass
from pathlib import Path
from irods.session import iRODSSession

from .environment import (
    check_iinit,
    check_irods_environment,
    EnvironmentError,
)


def python_session_from_env(envfile: str | None = None) -> iRODSSession:
    """
    Create an iRODS session using the user's iCommands-style irods_environment.json.
    Prompts the user for their password and validates the connection.
    """
    env_path = check_irods_environment(envfile)
    env = json.loads(env_path.read_text())

    # Extract password or ask for it
    password = env.get("irods_password")
    if not password:
        password = getpass("iRODS password: ")

    session = iRODSSession(
        irods_env_file=str(env_path),
        password=password,
    )

    # Validate connection
    session.server_version

    return session


def icommands_init() -> None:
    """
    Run `iinit` after verifying that iCommands are installed.
    Provides clear error messages if something is missing or misconfigured.
    """
    check_iinit()

    try:
        subprocess.run(["iinit"], check=True)
    except FileNotFoundError:
        raise EnvironmentError(
            "iinit was not found even though it should exist.\n"
            "This usually means your PATH is not set correctly."
        )
    except subprocess.CalledProcessError:
        raise EnvironmentError(
            "iinit failed. Your iRODS environment may be misconfigured.\n"
            "Try running `iinit` manually to diagnose the issue."
        )

