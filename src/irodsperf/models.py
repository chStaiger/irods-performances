from dataclasses import dataclass


@dataclass
class UploadResult:
    """Data class for results."""

    data: str
    duration: float
    checksum: bool
    client: str
