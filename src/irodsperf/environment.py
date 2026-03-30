import json
from pathlib import Path
import subprocess
from typing import Optional


class EnvironmentError(Exception):
    """Raised when required external tools or configuration are missing."""


def _command_exists(cmd: str) -> bool:
    result = subprocess.run(
        ["which", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


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
    This verifies:
      - iCommands are installed
      - the environment is initialized (iinit was run)
      - authentication works
      - the iRODS server is reachable
    """
    check_iinit()
    check_iput()

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
# Cadaver checks
# -----------------------------

def check_cadaver() -> None:
    if not _command_exists("cadaver"):
        raise EnvironmentError(
            "Cadaver (WebDAV client) is not installed. Install it via your package manager."
        )


def check_cadaver_credentials(
    netrc_path: Optional[str] = None,
    cadaverrc_path: Optional[str] = None,
) -> None:
    netrc = Path(netrc_path or Path.home() / ".netrc")
    cadaverrc = Path(cadaverrc_path or Path.home() / ".cadaverrc")

    if not netrc.exists():
        raise EnvironmentError(
            f"Cadaver requires a ~/.netrc file with WebDAV credentials. Missing: {netrc}"
        )

    if not cadaverrc.exists():
        raise EnvironmentError(
            f"Cadaver requires a ~/.cadaverrc file specifying the WebDAV endpoint. Missing: {cadaverrc}"
        )

    content = netrc.read_text()
    if "login" not in content or "password" not in content:
        raise EnvironmentError(
            f"{netrc} does not contain valid WebDAV login/password entries."
        )


# -----------------------------
# iRODS environment.json checks
# -----------------------------

def load_irods_environment(envfile: Optional[str] = None) -> dict:
    """
    Load and return the iRODS environment.json as a dict.
    Assumes check_irods_environment() has already validated it.
    """
    default_path = Path.home() / ".irods" / "irods_environment.json"
    env_path = Path(envfile) if envfile else default_path

    with env_path.open() as f:
        return json.load(f)


def check_irods_environment(envfile: Optional[str] = None) -> None:
    """
    Validate the iRODS environment.json file.
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
    """
    Validate that ~/.netrc and ~/.cadaverrc exist and contain the required
    WebDAV credentials and endpoint configuration.
    """
    netrc = Path(netrc_path or Path.home() / ".netrc")
    cadaverrc = Path(cadaverrc_path or Path.home() / ".cadaverrc")

    # Check existence
    if not netrc.exists():
        raise EnvironmentError(
            f"Cadaver requires a ~/.netrc file with WebDAV credentials. Missing: {netrc}"
        )

    if not cadaverrc.exists():
        raise EnvironmentError(
            f"Cadaver requires a ~/.cadaverrc file specifying the WebDAV endpoint. Missing: {cadaverrc}"
        )

    # Validate .netrc content
    content = netrc.read_text()
    if "login" not in content or "password" not in content:
        raise EnvironmentError(
            f"{netrc} does not contain valid WebDAV login/password entries."
        )

    # Validate .cadaverrc content
    cadaverrc_content = cadaverrc.read_text()
    if "http" not in cadaverrc_content:
        raise EnvironmentError(
            f"{cadaverrc} does not contain a valid WebDAV URL (expected something like 'http://host:port/path')."
        )

def test_cadaver_connection(url: str | None = None) -> None:
    """
    Attempt a real WebDAV connection using cadaver by issuing a harmless 'ls' command.
    If no URL is provided, the function attempts to read it from ~/.cadaverrc.
    """
    check_cadaver()  # ensure cadaver is installed

    # If no URL is provided, try to load it from ~/.cadaverrc
    if url is None:
        cadaverrc = Path.home() / ".cadaverrc"
        if not cadaverrc.exists():
            raise EnvironmentError(
                "No URL provided and ~/.cadaverrc not found. "
                "Provide a URL or create a .cadaverrc with an 'open <url>' line."
            )

        # Parse the URL from the 'open' line
        for line in cadaverrc.read_text().splitlines():
            line = line.strip()
            if line.startswith("open "):
                url = line.split(" ", 1)[1].strip()
                break

        if url is None:
            raise EnvironmentError(
                f"~/.cadaverrc exists but contains no 'open <url>' line:\n{cadaverrc}"
            )

    # Perform a real connection test
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
