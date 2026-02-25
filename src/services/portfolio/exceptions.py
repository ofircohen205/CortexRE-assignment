from __future__ import annotations

from fastapi import status

class PortfolioError(Exception):
    """Base class for portfolio service errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class DatasetNotFoundError(PortfolioError):
    """Raised when the dataset file cannot be found."""
    def __init__(self, path: str):
        super().__init__(f"Dataset and path {path} not found.", status_code=status.HTTP_404_NOT_FOUND)

class DataNormalizationError(PortfolioError):
    """Raised when normalization fails."""
    def __init__(self, detail: str):
        super().__init__(f"Data normalization failed: {detail}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
