from dataclasses import dataclass

@dataclass
class UploadResult:
    data: str
    duration: float
    checksum: bool
    client: str
