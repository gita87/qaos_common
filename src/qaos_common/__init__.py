"""Public package metadata and shared operational contracts."""

from .cancellation import CancellationToken
from .errors import QAOSCommonError
from .limits import DEFAULT_LIMITS, ProcessingLimits
from .progress import PROGRESS_STAGES, ProgressEvent

__version__ = "0.2.1"

__all__ = [
    "DEFAULT_LIMITS",
    "PROGRESS_STAGES",
    "CancellationToken",
    "ProcessingLimits",
    "ProgressEvent",
    "QAOSCommonError",
    "__version__",
]
