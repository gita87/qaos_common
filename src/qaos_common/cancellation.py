"""Thread-safe cooperative cancellation."""

from threading import Event

from .errors import ProcessCancelledError


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise ProcessCancelledError("Processing was cancelled")


__all__ = ["CancellationToken"]
