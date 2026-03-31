from pathlib import Path
import pickle

from .filegen import ensure_dir, create_file_gb, create_file_kb
from .session import python_session_from_env, icommands_init
from .uploaders import upload_python, upload_icommands, upload_webdav
from .cleanup import cleanup_irods, cleanup_local
from .environment import reset_perftest_collection, ensure_perftest_collection

from .environment import (
    check_iinit,
    check_iput,
    test_icommands_connection,
    check_irods_environment,
    test_python_irods_connection,
    check_cadaver,
    check_cadaver_credentials,
    test_cadaver_connection,
)


def run_all_tests(
    clients: list[str],
    large_sizes: list[int],
    num_small: int,
    small_size: int,
    output_file: str,
    datafolder: str = "/tmp/irodsperf_data",
):
    """
    Run a full iRODS performance benchmark using any combination of:
        - "icommands"
        - "python"
        - "webdav"

    The orchestrator generates test data, uploads it using the selected
    clients, measures upload times, and stores all results in a pickle file.

    Parameters
    ----------
    clients : list[str]
        A list of client backends to run. Valid values:
            - "icommands"  → uses iput/ils
            - "python"     → uses python-irodsclient
            - "webdav"     → uses cadaver WebDAV client

        You may specify any subset, e.g.:
            ["python", "webdav"]
            ["icommands"]
            ["icommands", "python", "webdav"]

    large_sizes : list[int]
        Sizes (in gigabytes) of the large test files to generate.
        Example: [1, 5] will create 1 GB and 5 GB files.

    num_small : int
        Number of small files to generate for the small-file test set.

    small_size : int
        Size (in kilobytes) of each small file.

    output_file : str
        Path to a pickle file where all UploadResult objects will be stored.
        The file will contain a list of UploadResult instances.

    datafolder : str, optional
        Directory where temporary test data will be created.
        Defaults to "/tmp/irodsperf_data".

    Behavior
    --------
    For each selected client, the orchestrator performs:

    1. **Environment validation**
       Ensures the backend is installed, configured, and can connect.

    2. **Large file uploads**
       Uploads all generated large files.

    3. **Small file uploads**
       Uploads all files in the generated small-file directory.

    4. **Checksum runs (where supported)**
       - iCommands: run once without checksum, once with checksum (-K)
       - python-irodsclient: run once without checksum, once with checksum
       - WebDAV: checksum not supported → single run

    5. **Cleanup**
       Removes the remote test collection and local temporary files.

    Output
    ------
    The pickle file contains a list of UploadResult objects, each with:
        - data: path of the uploaded file
        - duration: measured upload time (seconds)
        - checksum: whether checksum verification was enabled
        - client: backend used ("icommands", "python-x.y.z", "webdav")

    Usage Example
    -------------
    >>> run_all_tests(
    ...     clients=["icommands", "python"],
    ...     large_sizes=[1, 5],
    ...     num_small=100,
    ...     small_size=64,
    ...     output_file="results.pkl",
    ... )

    This will:
        - Generate 1 GB and 5 GB files
        - Generate 100 × 64 KB small files
        - Upload everything using iCommands (with and without checksum)
        - Upload everything using python-irodsclient (with and without checksum)
        - Save all results to results.pkl
    """

    results = []

    # -----------------------------
    # Prepare local test data
    # -----------------------------
    print("Prepare local test data ...")
    datafolder = Path(datafolder)
    ensure_dir(datafolder)

    # Large files
    large_files = [create_file_gb(datafolder, s) for s in large_sizes]

    # Small files
    small_dir = ensure_dir(datafolder / "smallfiles")
    small_files = []
    for i in range(num_small):
        f = create_file_kb(small_dir, small_size, str(i))
        small_files.append(f)

    # -----------------------------
    # Run selected clients
    # -----------------------------
    for client in clients:
        # ============================================================
        # iCommands
        # ============================================================
        if client == "icommands":
            print("Running iCommands tests…")

            check_iinit()
            check_iput()
            test_icommands_connection()

            icommands_init()

            collpath = "perfTest"
            reset_perftest_collection("icommands", "perfTest")

            # ---- Run 1: without checksum ----
            print("\tNo checksum tests ...")
            for f in large_files:
                result = upload_icommands(f, collpath, checksum=False)
                results.append(result)

            # Upload folder with small files
            result = upload_icommands(small_dir, collpath, checksum=False, recursive = True)
            results.append(result)

            # ---- Run 2: with checksum ----
            print("\tClean up ...")
            reset_perftest_collection("icommands", "perfTest")
            print("\tCecksum tests ...")
            for f in large_files:
                result = upload_icommands(f, collpath, checksum=True)
                results.append(result)

            # Upload folder with small files
            result = upload_icommands(small_dir, collpath, checksum=True, recursive = True)
            results.append(result)

            cleanup_irods(collpath, "icommands")

        # ============================================================
        # python-irodsclient
        # ============================================================
        elif client == "python":
            print("Running python-irodsclient tests…")

            env_path = check_irods_environment()
            test_python_irods_connection()

            session = python_session_from_env()
            if session.get_irods_env(env_path).get("irods_home"):
                home = session.get_irods_env(env_path).get("irods_home")
                collpath = f"{home}/perfTest"
            else:
                collpath = f"/{session.zone}/home/{session.username}/perfTest"
            print(f"Uploading to {collpath}")
            ensure_perftest_collection(client, collpath, session)
            reset_perftest_collection(client, collpath, session)

            # ---- Run 1: without checksum ----
            print("\tNo checksum tests ...")
            for f in large_files:
                result = upload_python(f, collpath, session, checksum=False)
                results.append(result)

            result = upload_python(small_dir, collpath, session, checksum=False, recursive = True)
            results.append(result)

            # ---- Run 2: with checksum ----
            print("\tCleanup ...")
            reset_perftest_collection(client, collpath, session)
            print("\tChecksum tests ...")
            for f in large_files:
                result = upload_python(f, collpath, session, checksum=True)
                results.append(result)

            result = upload_python(small_dir, collpath, session, checksum=True, recursive = True)
            results.append(result)

            cleanup_irods(collpath, "python", session=session)

        # ============================================================
        # WebDAV / cadaver
        # ============================================================
        elif client == "webdav":
            print("Running WebDAV (cadaver) tests…")

            check_cadaver()
            check_cadaver_credentials()
            test_cadaver_connection()

            collpath = "perfTest"
            ensure_perftest_collection(client, collpath)
            reset_perftest_collection(client, collpath)
            print("\tNo checksum tests ...")

            # WebDAV does not support checksum
            for f in large_files:
                result = upload_webdav(f, collpath)
                results.append(result)

            result = upload_webdav(small_dir, collpath)
            results.append(result)

            cleanup_irods(collpath, "cadaver")

        else:
            raise ValueError(f"Unknown client: {client}")

    # -----------------------------
    # Save results
    # -----------------------------
    print("Save results ...")
    with open(output_file, "wb") as f:
        pickle.dump(results, f)

    # -----------------------------
    # Cleanup local files
    # -----------------------------
    print("Cleanup local data...")
    cleanup_local(datafolder)
