import json
import subprocess
from pathlib import Path
from irods.exception import CAT_INVALID_AUTHENTICATION
from irods.exception import NetworkException


class PerfEnvironmentError(Exception):
    """Raised when required external tools or configuration are missing."""


# -----------------------------
# Utility
# -----------------------------

def _command_exists(cmd: str) -> bool:
    result = subprocess.run(
        ["which", cmd],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

# -----------------------------
# Collection creation
# -----------------------------

def ensure_perftest_collection(client: str, collpath: str, session=None) -> None:
    """Ensure that the performance test collection exists for the given client.

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
    print(f"Ensure {collpath}")
    # iCommands
    if client == "icommands":
        subprocess.run(
            ["imkdir", "-p", collpath],
            check=False,
            capture_output=True,
            text=True,
        )
        return

    # python-irodsclient
    if client == "python":
        if session is None:
            raise PerfEnvironmentError("python client requires a session for collection creation")
    
        # Ensure the full path exists, creating parents as needed
        from pathlib import PurePosixPath
        from irods.exception import CollectionDoesNotExist
    
        p = PurePosixPath(collpath)
        parts = p.parts
    
        # Start with "/zone"
        current = PurePosixPath(parts[0]) / parts[1]
    
        # Ensure zone root exists
        try:
            session.collections.get(str(current))
        except CollectionDoesNotExist:
            session.collections.create(str(current))
    
        # Create deeper components
        for part in parts[2:]:
            current = current / part
            try:
                session.collections.get(str(current))
            except CollectionDoesNotExist:
                session.collections.create(str(current))
    
        return

    # WebDAV / cadaver
    if client == "webdav":
        cadaverrc = Path.home() / ".cadaverrc"
        url = None
        for line in cadaverrc.read_text().splitlines():
            if line.strip().startswith("open "):
                url = line.split(" ", 1)[1].strip()
                break

        if url is None:
            raise PerfEnvironmentError("Could not find 'open <url>' in ~/.cadaverrc")

        mkdir_cmd = f"mkdir {collpath}\nquit\n"
        subprocess.run(
            ["cadaver", url],
            check=False, input=mkdir_cmd,
            text=True,
            capture_output=True,
        )
        return

    raise ValueError(f"Unknown client: {client}")

# -----------------------------
# iRODS environment.json checks
# -----------------------------

def check_irods_environment(envfile: str | None = None) -> Path:
    """Validate the iRODS environment.json file (iCommands format).

    Returns the resolved Path.
    """
    default_path = Path.home() / ".irods" / "irods_environment.json"
    env_path = Path(envfile) if envfile else default_path

    if not env_path.exists():
        raise PerfEnvironmentError(
            f"iRODS environment file not found. Expected at: {env_path}\n"
            "Run `iinit` or create the file manually.",
        )

    try:
        data = json.loads(env_path.read_text())
    except json.JSONDecodeError:
        raise PerfEnvironmentError(f"Invalid JSON in {env_path}")

    required = [
        "irods_host",
        "irods_port",
        "irods_user_name",
        "irods_zone_name",
    ]

    missing = [key for key in required if key not in data]
    if missing:
        raise PerfEnvironmentError(
            f"iRODS environment file {env_path} is missing required fields: {', '.join(missing)}",
        )

    return env_path


# -----------------------------
# iCommands checks
# -----------------------------

def check_iinit() -> None:
    """Verify that `iinit` exists on PATH."""
    if not _command_exists("iinit"):
        raise PerfEnvironmentError
        (
            "iinit not found. iCommands appear to be missing or not on your PATH.\n"
            "Ensure the iCommands bin directory is included in your PATH.",
        )


def check_iput() -> None:
    """Verify that `iput` exists on PATH."""
    if not _command_exists("iput"):
        raise PerfEnvironmentError(
            "iput not found. Install iRODS iCommands and ensure they are on your PATH.",
        )


def test_icommands_connection() -> None:
    """Perform a real iCommands connection test by running `ils`.

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
        check=False,
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        raise PerfEnvironmentError(
            "iCommands appear to be installed but cannot connect to the iRODS server.\n"
            f"Output:\n{proc.stdout}\nErrors:\n{proc.stderr}\n"
            "Try running `iinit` again or verify your irods_environment.json.",
        )


# -----------------------------
# python-irodsclient checks
# -----------------------------

def test_python_irods_connection(envfile: str | None = None) -> None:
    """Perform a real connection test using python-irodsclient.

    SSL settings are automatically loaded from irods_environment.json.
    """
    # Import inside the function to avoid circular imports
    from irodsperf.session import python_session_from_env
    env_path = check_irods_environment(envfile)
    _ = json.loads(env_path.read_text())

    try:
        session = python_session_from_env(envfile)
        print(f"Connected to {session.zone}")
    except CAT_INVALID_AUTHENTICATION:
        raise PerfEnvironmentError("Invalid iRODS credentials for python-irodsclient.")
    except NetworkException as e:
        raise PerfEnvironmentError(f"Cannot reach iRODS server: {e}")
    except Exception as e:
        raise PerfEnvironmentError(f"Unexpected python-irodsclient error: {e}")
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
        raise PerfEnvironmentError(
            "Cadaver (WebDAV client) is not installed. Install it via your package manager.",
        )


def check_cadaver_credentials(
    netrc_path: str | None = None,
    cadaverrc_path: str | None = None,
) -> None:
    """Validate that cadaver has enough information to authenticate.

    Accepts:
      - ~/.netrc with login/password
      - OR ~/.cadaverrc with embedded credentials
      - OR ~/.cadaverrc with a plain URL (server may prompt)
    """
    netrc = Path(netrc_path or Path.home() / ".netrc")
    cadaverrc = Path(cadaverrc_path or Path.home() / ".cadaverrc")

    # ~/.cadaverrc is required because it contains the WebDAV URL
    if not cadaverrc.exists():
        raise PerfEnvironmentError(f"Missing ~/.cadaverrc: {cadaverrc}")

    cadaverrc_content = cadaverrc.read_text()

    # Extract the URL from "open <url>"
    url = None
    for line in cadaverrc_content.splitlines():
        if line.strip().startswith("open "):
            url = line.split(" ", 1)[1].strip()
            break

    if url is None:
        raise PerfEnvironmentError(
            f"{cadaverrc} does not contain a valid 'open <url>' line.",
        )

    # Case 1: URL contains credentials → OK
    if "@" in url and "://" in url:
        return

    # Case 2: ~/.netrc exists and contains login/password → OK
    if netrc.exists():
        content = netrc.read_text()
        if "login" in content and "password" in content:
            return

    # Case 3: ~/.cadaverrc contains username/password → OK
    if "username" in cadaverrc_content and "password" in cadaverrc_content:
        return

    raise PerfEnvironmentError("Cadaver has no credentials available.")


def test_cadaver_connection(url: str | None = None) -> None:
    """Attempt a real WebDAV connection using cadaver by issuing a harmless 'ls' command.

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
            raise PerfEnvironmentError(
                f"{cadaverrc} exists but contains no 'open <url>' line.",
            )

    proc = subprocess.run(
        ["cadaver", url],
        check=False, input="ls\nquit\n",
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        raise PerfEnvironmentError(
            f"Cadaver could not connect to {url}.\n"
            f"Output:\n{proc.stdout}\nErrors:\n{proc.stderr}",
        )

def reset_perftest_collection(client: str, collpath: str, session=None) -> None:
    """Ensure the perftest collection exists and is empty.

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
    # iCommands
    if client == "icommands":
        # Ensure collection exists
        subprocess.run(["imkdir", "-p", collpath], check=True)

        proc = subprocess.run(
            ["ils", "-l", collpath],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in proc.stdout.splitlines():
            stripped = line.strip()

            if stripped.endswith(":"):
                continue

            if stripped.startswith("C-"):
                subcoll = stripped.split()[-1]
                subprocess.run(["irm", "-rf", subcoll], check=True)
                continue

            if stripped:
                filename = stripped.split()[-1]
                full = f"{collpath}/{filename}"
                subprocess.run(["irm", "-f", full], check=True)

        return

    # python-irodsclient
    if client == "python":
        if session is None:
            msg = "python client requires a session for collection reset"
            raise PerfEnvironmentError(msg)

        try:
            coll = session.collections.get(collpath)
        except Exception:
            session.collections.create(collpath)
            coll = session.collections.get(collpath)

        objs = list(coll.data_objects)
        subs = list(coll.subcollections)

        for obj in objs:
            session.data_objects.unlink(obj.path, force=True)

        for sub in subs:
            session.collections.remove(sub.path, recurse=True, force=True)

        return

    # WebDAV / cadaver
    if client == "webdav":
        cadaverrc = Path.home() / ".cadaverrc"
        url = None
        for line in cadaverrc.read_text().splitlines():
            if line.strip().startswith("open "):
                url = line.split(" ", 1)[1].strip()
                break

        if url is None:
            msg = "Could not find 'open <url>' in ~/.cadaverrc"
            raise PerfEnvironmentError(msg)

        # Create collection if missing
        subprocess.run(
            ["cadaver", url],
            check=False, input=f"mkdir {collpath}\nquit\n",
            text=True,
            capture_output=True,
        )

        # Remove all contents
        subprocess.run(
            ["cadaver", url],
            check=False, input=f"cd {collpath}\nls\nmrm *\nquit\n",
            text=True,
            capture_output=True,
        )
        return

    msg = f"Unknown client: {client}"
    raise ValueError(msg)
