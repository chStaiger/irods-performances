import time
import subprocess
import os
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
    recursive: bool = False,
    resource: str | None = None,
) -> UploadResult:

    filepath = Path(filepath)

    # Build iRODS put options
    opts = {}
    if checksum:
        opts[kw.REG_CHKSUM_KW] = ""
    if resource:
        opts[kw.RESC_NAME_KW] = resource

    # Ensure target collection exists
    try:
        session.collections.get(collpath)
    except Exception:
        session.collections.create(collpath)

    # --- CASE 1: recursive directory upload ---
    if recursive and filepath.is_dir():
        for root, dirs, files in os.walk(filepath):
            root = Path(root)

            # Compute relative path inside the collection
            rel = root.relative_to(filepath)
            target_coll = Path(collpath) / rel

            # Ensure collection exists in iRODS
            try:
                session.collections.get(str(target_coll))
            except Exception:
                session.collections.create(str(target_coll))

            # Upload files in this directory
            for fname in files:
                src = root / fname
                dst = target_coll / fname
                session.data_objects.put(str(src), str(dst), **opts)

        return UploadResult(
            data=str(filepath),
            duration=0.0,  # filled by decorator
            checksum=checksum,
            client=f"python-{irods.__version__}",
        )

    # --- CASE 2: single file upload ---
    session.data_objects.put(
        str(filepath),
        f"{collpath}/{filepath.name}",
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
    localpath: str | Path,
    collpath: str,
    checksum: bool = False,
    recursive: bool = False,
    resource: str | None = None,
) -> UploadResult:

    localpath = Path(localpath)

    # Detect whether directory contains subdirectories
    contains_subdirs = False
    if localpath.is_dir():
        for entry in localpath.iterdir():
            if entry.is_dir():
                contains_subdirs = True
                break

    cmd = ["iput"]

    # --- Choose correct flags ---
    if recursive:
        if contains_subdirs:
            # Nested directories → cannot use -b
            cmd.append("-r")
        else:
            # Flat directory → bulk recursive works
            cmd.append("-br")
    else:
        # Non-recursive upload (single file or flat directory)
        cmd.append("-b")

    # Checksum
    if checksum:
        cmd.append("-K")

    # Resource
    if resource:
        cmd += ["-R", resource]

    # Paths
    cmd += [str(localpath), collpath]

    # Run command
    subprocess.run(cmd, check=True)

    return UploadResult(
        data=str(localpath),
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
    Upload a file or directory using cadaver.
    Assumes ~/.cadaverrc contains: open <url>, username, password.
    """
    filepath = Path(filepath)

    # Load WebDAV base URL from ~/.cadaverrc
    cadaverrc = Path.home() / ".cadaverrc"
    url = None
    for line in cadaverrc.read_text().splitlines():
        if line.strip().startswith("open "):
            url = line.split(" ", 1)[1].strip()
            break

    if url is None:
        raise RuntimeError("Could not find 'open <url>' in ~/.cadaverrc")

    # --- CASE 1: recursive directory upload ---
    if filepath.is_dir():
        for root, dirs, files in os.walk(filepath):
            root = Path(root)

            # Compute relative path inside the collection
            rel = root.relative_to(filepath)
            target_coll = Path(collpath) / rel

            # Create directory in WebDAV
            cadaver_input = f"mkdir {target_coll}\nquit\n"
            subprocess.run(
                ["cadaver", url],
                input=cadaver_input,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Upload files in this directory
            for fname in files:
                src = root / fname
                dst = target_coll / fname

                cadaver_input = (
                    f"cd {target_coll}\n"
                    f"put {src}\n"
                    f"quit\n"
                )

                proc = subprocess.run(
                    ["cadaver", url],
                    input=cadaver_input,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                if proc.returncode != 0:
                    raise RuntimeError(
                        f"WebDAV upload failed for {src}.\n"
                        f"Output:\n{proc.stdout}\nErrors:\n{proc.stderr}"
                    )

        return UploadResult(
            data=str(filepath),
            duration=0.0,  # filled by decorator
            checksum=False,
            client="webdav",
        )

    # --- CASE 2: single file upload ---
    cadaver_input = (
        f"cd {collpath}\n"
        f"put {filepath}\n"
        f"quit\n"
    )

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

