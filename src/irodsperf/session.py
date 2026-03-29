import subprocess
from getpass import getpass
from pathlib import Path
from irods.session import iRODSSession

from .environment import (
    check_irods_environment,
    check_iinit,
    EnvironmentError,
)


def python_session_from_env(envfile: str | None = None) -> iRODSSession:
    """
    Create an iRODS session using the user's irods_environment.json.
    Prompts the user for their password and validates the connection.
    """
    # Validate environment file
    check_irods_environment(envfile)

    env_path = Path(envfile) if envfile else Path.home() / ".irods" / "irods_environment.json"

    # Prompt for password (same behavior as iinit)
    password = getpass("iRODS password: ")

    # Create session using python-irodsclient's built-in loader
    session = iRODSSession(
        irods_env_file=str(env_path),
        password=password,
    )

    # Force a server connection to validate credentials and config
    session.server_version()

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
            "This usually means your PATH is not set correctly.\n"
            "Ensure the iCommands bin directory is included in your PATH."
        )
    except subprocess.CalledProcessError:
        raise EnvironmentError(
            "iinit failed. Your iRODS environment may be misconfigured.\n"
            "Try running `iinit` manually to diagnose the issue."
        )

