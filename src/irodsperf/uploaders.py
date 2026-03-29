import time
import subprocess
from pathlib import Path
from irods.session import iRODSSession
import irods.keywords as kw
import irods
from .models import UploadResult


def _timed(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        func(*args, **kwargs)
        end = time.perf_counter()
        return end - start
    return wrapper


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

    session.collections.create(collpath)
    session.data_objects.put(
        str(filepath),
        f"{collpath}/{Path(filepath).name}",
        **opts,
    )

    return UploadResult(
        data=str(filepath),
        duration=0.0,
        checksum=checksum,
        client=f"python-{irods.__version__}",
    )


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


@_timed
def upload_webdav(filepath: str | Path, collpath: str) -> UploadResult:
    cmd = f"echo 'cd {collpath}\nput {filepath}' | cadaver"
    subprocess.run(cmd, shell=True, check=True)

    return UploadResult(
        data=str(filepath),
        duration=0.0,
        checksum=False,
        client="webdav",
    )

