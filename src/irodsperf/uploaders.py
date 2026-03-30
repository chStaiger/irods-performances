import time
import subprocess
from pathlib import Path
from irods.session import iRODSSession
import irods.keywords as kw
import irods

from .models import UploadResult


# -----------------------------
# Timing decorator (fixed)
# -----------------------------

def _timed(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()

        # Inject duration into UploadResult
        result.duration = end - start
        return result

    return wrapper


# -----------------------------
# Python iRODS client uploader
# -----------------------------

@_timed
def upload_python(
    filepath: str | Path,
    collpath: str,
    session: iRODSSession,
    checksum: bool = False,
    resource: str | None = None,
) -> UploadResult:

    opts = {}
    if checksum:
        opts[kw.REG_CHKSUM_KW] = ""
    if resource:
        opts[kw.RESC_NAME_KW] = resource

    # Ensure collection exists
    try:
        session.collections.get(collpath)
    except Exception:
        session.collections.create(collpath)

    # Upload
    session.data_objects.put(
        str(filepath),
        f"{collpath}/{Path(filepath).name}",
        **opts,
    )

    return UploadResult(
        data=str(filepath),
        duration=0.0,  # filled by decorator
        checksum=checksum,
        client=f"python-{irods.__version__}",
    )


# -----------------------------
# iCommands uploader
# -----------------------------

@_timed
def upload_icommands(
    filepath: str | Path,
    collpath: str,
    checksum: bool = False,
    resource: str | None = None,
) -> UploadResult:

    cmd = ["iput", "-bf"]
    if checksum:
        cmd.append("-K")
    if resource:
        cmd += ["-R", resource]

    cmd += [str(filepath), collpath]

    subprocess.run(cmd, check=True)

    return UploadResult(
        data=str(filepath),
        duration=0.0,
        checksum=checksum,
        client="icommands",
    )


# -----------------------------
# WebDAV uploader (cadaver)
# -----------------------------

@_timed
def upload_webdav(filepath: str | Path, collpath: str) -> UploadResult:
    """
    Upload using cadaver. Assumes environment + credentials already validated.
    """

    # Load URL from ~/.cadaverrc
    cadaverrc = Path.home() / ".cadaverrc"
    url = None
    for line in cadaverrc.read_text().splitlines():
        if line.strip().startswith("open "):
            url = line.split(" ", 1)[1].strip()
            break

    if url is None:
        raise RuntimeError("Could not find 'open <url>' in ~/.cadaverrc")

    # Use stdin input instead of shell echo for safety
    cadaver_input = f"cd {collpath}\nput {filepath}\nquit\n"

    proc = subprocess.run(
        ["cadaver", url],
        input=cadaver_input,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"WebDAV upload failed.\nOutput:\n{proc.stdout}\nErrors:\n{proc.stderr}"
        )

    return UploadResult(
        data=str(filepath),
        duration=0.0,
        checksum=False,
        client="webdav",
    )

