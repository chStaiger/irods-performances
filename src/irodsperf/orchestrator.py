from pathlib import Path
import pickle
from .filegen import ensure_dir, create_file_gb, create_file_kb
from .session import python_session, icommands_init
from .uploaders import upload_python, upload_icommands, upload_webdav
from .cleanup import cleanup_irods, cleanup_local

from .environment import (
    check_icommands,
    check_cadaver,
    check_cadaver_credentials,
    check_irods_environment,
)


def run_all_tests(
    clients: list[str],
    large_sizes: list[int],
    num_small: int,
    small_size: int,
    output_file: str,
    datafolder: str = "/tmp/irodsperf_data",
):
    results = []

    datafolder = Path(datafolder)
    ensure_dir(datafolder)

    # Large files
    large_files = [create_file_gb(datafolder, s) for s in large_sizes]

    # Small files
    small_dir = ensure_dir(datafolder / "smallfiles")
    for i in range(num_small):
        create_file_kb(small_dir, small_size, str(i))

    for client in clients:
        if client == "icommands":
            icommands_init()
            collpath = "perfTest"

            for f in large_files:
                dur = upload_icommands(f, collpath)
                results.append((str(f), dur, False, "icommands"))

            cleanup_irods(collpath, "icommands")

        elif client == "python":
            check_irods_environment()  # validate ~/.irods/irods_environment.json
            session = python_session(
                password="MYPASSWD",
                host="MYHOST",
                user="MYUSER",
                zone="MYZONE",
            )
            collpath = f"/{session.zone}/home/{session.username}/perfTest"

            for f in large_files:
                dur = upload_python(f, collpath, session)
                results.append((str(f), dur, False, f"python"))

            cleanup_irods(collpath, "python", session=session)

        elif client == "cadaver":
            for f in large_files:
                dur = upload_webdav(f, "perfTest")
                results.append((str(f), dur, False, "webdav"))

            cleanup_irods("perfTest", "cadaver")

    with open(output_file, "wb") as f:
        pickle.dump(results, f)

    cleanup_local(datafolder)

