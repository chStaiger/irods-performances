import json
from pathlib import Path
import subprocess
from typing import Optional
from irods.session import iRODSSession
from irods.exception import NetworkException, CAT_INVALID_AUTHENTICATION


class EnvironmentError(Exception):
    """Raised when required external tools or configuration are missing."""


# -----------------------------
# Utility
# -----------------------------

def _command_exists(cmd: str) -> bool:
    result = subprocess.run(
        ["which", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def ensure_perftest_collection(client: str, collpath: str, session=None) -> None:
    """
    Ensure that the performance test collection exists for the given client.
    This operation is NOT timed and should be called before uploads.

    Parameters
    ----------
    client : str
        One of: "icommands", "python", "webdav"

    collpath : str
        The collection path to create (e.g. "perfTest" or "/zone/home/user/perfTest")

    session : iRODSSession, optional
        Required only for python-irodsclient.
    """

    # -----------------------------
    # iCommands
    # -----------------------------
    if client == "icommands":
        subprocess.run(
            ["imkdir", "-p", collpath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return

    # -----------------------------
    # python-irodsclient
    # -----------------------------
    if client == "python":
        if session is None:
            raise EnvironmentError("python client requires a session for collection creation")

        try:
            session.collections.get(collpath)
        except Exception:
            session.collections.create(collpath)
        return

    # -----------------------------
    # WebDAV / cadaver
    # -----------------------------
    if client == "webdav":
        cadaverrc = Path.home() / ".cadaverrc"
        url = None
        for line in cadaverrc.read_text().splitlines():
            if line.strip().startswith("open "):
                url = line.split(" ", 1)[1].strip()
                break

        if url is None:
            raise EnvironmentError("Could not find 'open <url>' in ~/.cadaverrc")

        mkdir_cmd = f"mkdir {collpath}\nquit\n"
        subprocess.run(
            ["cadaver", url],
            input=mkdir_cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return

    raise ValueError(f"Unknown client: {client}")


# -----------------------------
# iRODS environment.json checks
# -----------------------------

def check_irods_environment(envfile: Optional[str] = None) -> Path:
    """
    Validate the iRODS environment.json file (iCommands format).
    Returns the resolved Path.
    """
    default_path = Path.home() / ".irods" / "irods_environment.json"
    env_path = Path(envfile) if envfile else default_path

    if not env_path.exists():
        raise EnvironmentError(
            f"iRODS environment file not found. Expected at: {env_path}\n"
            "Run `iinit` or create the file manually."
        )

    try:
        data = json.loads(env_path.read_text())
    except json.JSONDecodeError:
        raise EnvironmentError(f"Invalid JSON in {env_path}")

    required = [
        "irods_host",
        "irods_port",
        "irods_user_name",
        "irods_zone_name",
    ]

    missing = [key for key in required if key not in data]
    if missing:
        raise EnvironmentError(
            f"iRODS environment file {env_path} is missing required fields: {', '.join(missing)}"
        )

    return env_path


def load_irods_environment(envfile: Optional[str] = None) -> dict:
    """Load and return the iRODS environment.json as a dict."""
    env_path = check_irods_environment(envfile)
    return json.loads(env_path.read_text())


# -----------------------------
# iCommands checks
# -----------------------------

def check_iinit() -> None:
    """Verify that `iinit` exists on PATH."""
    if not _command_exists("iinit"):
        raise EnvironmentError(
            "iinit not found. iCommands appear to be missing or not on your PATH.\n"
            "Ensure the iCommands bin directory is included in your PATH."
        )


def check_iput() -> None:
    """Verify that `iput` exists on PATH."""
    if not _command_exists("iput"):
        raise EnvironmentError(
            "iput not found. Install iRODS iCommands and ensure they are on your PATH."
        )


def test_icommands_connection() -> None:
    """
    Perform a real iCommands connection test by running `ils`.
    Verifies:
      - iCommands installed
      - environment initialized (iinit)
      - authentication works
      - server reachable
    """
    check_iinit()
    check_iput()
    check_irods_environment()

    proc = subprocess.run(
        ["ils"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if proc.returncode != 0:
        raise EnvironmentError(
            "iCommands appear to be installed but cannot connect to the iRODS server.\n"
            f"Output:\n{proc.stdout}\nErrors:\n{proc.stderr}\n"
            "Try running `iinit` again or verify your irods_environment.json."
        )


# -----------------------------
# python-irodsclient checks
# -----------------------------

def test_python_irods_connection(envfile: Optional[str] = None) -> None:
    """
    Perform a real connection test using python-irodsclient.
    SSL settings are automatically loaded from irods_environment.json.
    """

    # Import inside the function to avoid circular imports
    from irodsperf.session import python_session_from_env
    env_path = check_irods_environment(envfile)
    env = json.loads(env_path.read_text())

    try:
        session = python_session_from_env(envfile)
        print(f"Connected to {session.zone}")
    except CAT_INVALID_AUTHENTICATION:
        raise EnvironmentError("Invalid iRODS credentials for python-irodsclient.")
    except NetworkException as e:
        raise EnvironmentError(f"Cannot reach iRODS server: {e}")
    except Exception as e:
        raise EnvironmentError(f"Unexpected python-irodsclient error: {e}")
    finally:
        try:
            session.cleanup()
        except Exception:
            pass


# -----------------------------
# Cadaver (WebDAV) checks
# -----------------------------

def check_cadaver() -> None:
    """Verify that the cadaver WebDAV client is installed."""
    if not _command_exists("cadaver"):
        raise EnvironmentError(
            "Cadaver (WebDAV client) is not installed. Install it via your package manager."
        )


def check_cadaver_credentials(
    netrc_path: Optional[str] = None,
    cadaverrc_path: Optional[str] = None,
) -> None:
    """Validate that ~/.netrc and ~/.cadaverrc exist and contain required fields."""
    netrc = Path(netrc_path or Path.home() / ".netrc")
    cadaverrc = Path(cadaverrc_path or Path.home() / ".cadaverrc")

    if not netrc.exists():
        raise EnvironmentError(f"Missing ~/.netrc: {netrc}")

    if not cadaverrc.exists():
        raise EnvironmentError(f"Missing ~/.cadaverrc: {cadaverrc}")

    content = netrc.read_text()
    if "login" not in content or "password" not in content:
        raise EnvironmentError(f"{netrc} does not contain valid login/password entries.")

    cadaverrc_content = cadaverrc.read_text()
    if "http" not in cadaverrc_content:
        raise EnvironmentError(
            f"{cadaverrc} does not contain a valid WebDAV URL (expected 'open http://...')."
        )


def test_cadaver_connection(url: str | None = None) -> None:
    """
    Attempt a real WebDAV connection using cadaver by issuing a harmless 'ls' command.
    If no URL is provided, load it from ~/.cadaverrc.
    """
    check_cadaver()
    check_cadaver_credentials()

    if url is None:
        cadaverrc = Path.home() / ".cadaverrc"
        for line in cadaverrc.read_text().splitlines():
            if line.strip().startswith("open "):
                url = line.split(" ", 1)[1].strip()
                break
        if url is None:
            raise EnvironmentError(
                f"{cadaverrc} exists but contains no 'open <url>' line."
            )

    proc = subprocess.run(
        ["cadaver", url],
        input="ls\nquit\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        raise EnvironmentError(
            f"Cadaver could not connect to {url}.\n"
            f"Output:\n{proc.stdout}\nErrors:\n{proc.stderr}"
        )

def reset_perftest_collection(client: str, collpath: str, session=None) -> None:
    """
    Ensure the perftest collection exists and is empty.
    This operation is NOT timed and should be called before uploads.

    Parameters
    ----------
    client : str
        One of: "icommands", "python", "webdav"

    collpath : str
        The collection path to prepare (e.g. "perfTest" or "/zone/home/user/perfTest")

    session : iRODSSession, optional
        Required only for python-irodsclient.
    """

    # ------------------------------------------------------------
    # iCommands
    # ------------------------------------------------------------
    if client == "icommands":
        # Create collection if missing
        subprocess.run(["imkdir", "-p", collpath])

        # Remove all contents
        subprocess.run(["irm", "-rf", f"{collpath}/*"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return

    # ------------------------------------------------------------
    # python-irodsclient
    # ------------------------------------------------------------
    if client == "python":
        if session is None:
            raise EnvironmentError("python client requires a session for collection reset")

        # Create collection if missing
        try:
            coll = session.collections.get(collpath)
        except Exception:
            session.collections.create(collpath)
            coll = session.collections.get(collpath)

        # Remove all data objects
        for obj in coll.data_objects:
            session.data_objects.unlink(obj.path, force=True)

        # Remove all subcollections
        for sub in coll.subcollections:
            session.collections.remove(sub.path, recurse=True, force=True)

        return

    # ------------------------------------------------------------
    # WebDAV / cadaver
    # ------------------------------------------------------------
    if client == "webdav":
        cadaverrc = Path.home() / ".cadaverrc"
        url = None
        for line in cadaverrc.read_text().splitlines():
            if line.strip().startswith("open "):
                url = line.split(" ", 1)[1].strip()
                break

        if url is None:
            raise EnvironmentError("Could not find 'open <url>' in ~/.cadaverrc")

        # Create collection if missing
        subprocess.run(
            ["cadaver", url],
            input=f"mkdir {collpath}\nquit\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Remove all contents
        subprocess.run(
            ["cadaver", url],
            input=f"cd {collpath}\nls\nmrm *\nquit\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return

    raise ValueError(f"Unknown client: {client}")


