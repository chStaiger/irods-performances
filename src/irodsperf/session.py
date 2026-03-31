import json
import subprocess
from getpass import getpass
from irods.session import iRODSSession
from .environment import EnvironmentError
from .environment import check_iinit
from .environment import check_irods_environment


def python_session_from_env(envfile: str | None = None) -> iRODSSession:
    """Create an iRODS session using the user's iCommands-style irods_environment.json.

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

def icommands_init(envfile: str | None = None) -> None:
    """Run `iinit` using the password from irods_environment.json if available.

    Falls back to interactive mode if no password is stored.
    """
    check_iinit()

    # Load environment file (same helper as python_session_from_env)
    env_path = check_irods_environment(envfile)
    env = json.loads(env_path.read_text())

    password = env.get("irods_password")

    # --- CASE 1: Password available → run iinit non-interactively ---
    if password:
        try:
            _ = subprocess.run(
                ["iinit"],
                input=password + "\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return
        except subprocess.CalledProcessError as e:
            raise EnvironmentError(
                f"iinit failed using password from environment file.\n"
                f"Output:\n{e.stdout}\nErrors:\n{e.stderr}"
            )

    # --- CASE 2: No password → fall back to interactive iinit ---
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

