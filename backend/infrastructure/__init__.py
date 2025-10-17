"""Infrastructure layer exports."""

from .ocr import OCRClient, OCRExtractionResult, configure_ocr_client, get_ocr_client
from .workspaces import InMemoryWorkspaceRepository, WorkspaceRepository

__all__ = [
    "InMemoryWorkspaceRepository",
    "WorkspaceRepository",
    "OCRClient",
    "OCRExtractionResult",
    "configure_ocr_client",
    "get_ocr_client",
]
