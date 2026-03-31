import platform
import subprocess
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """Check and create dir."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_sparse_file(fname: Path, size: int, unit: str) -> None:
    """Internal helper to create a sparse file of given size and unit.

    unit: 'k' for KB, 'g' for GB
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        # mkfile uses lowercase units: k, m, g
        subprocess.run(["mkfile", "-n", f"{size}{unit}", str(fname)], check=True)
    else:
        # fallocate uses uppercase units: K, M, G
        subprocess.run(["fallocate", "-l", f"{size}{unit.upper()}", str(fname)], check=True)


def create_file_gb(path: str | Path, size_gb: int) -> Path:
    """Create a file of size in GB."""
    path = Path(path)
    fname = path / f"data{size_gb}GB.img"
    _create_sparse_file(fname, size_gb, "g")
    return fname


def create_file_kb(path: str | Path, size_kb: int, name: str) -> Path:
    """Create a file of size in KB."""
    path = Path(path)
    fname = path / f"data{size_kb}KB.img_{name}"
    _create_sparse_file(fname, size_kb, "k")
    return fname

