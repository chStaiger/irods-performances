import subprocess
from pathlib import Path
from irods.session import iRODSSession


def cleanup_irods(collpath: str, client: str, session: iRODSSession | None = None):
    """Remove collection from iRODS with icommands, python or webdav."""
    if client == "icommands":
        subprocess.run(["irm", "-r", collpath], check=True)
        subprocess.run(["irmtrash"], check=True)

    elif client == "python" and session:
        coll = session.collections.get(collpath)
        coll.remove(recurse=True, force=True)

    elif client == "cadaver":
        cmd = f"echo 'rmcol {collpath}' | cadaver"
        subprocess.run(cmd, shell=True, check=True)


def cleanup_local(path: str | Path):
    """Remove local data folder."""
    subprocess.run(["rm", "-rf", str(path)], check=True)

