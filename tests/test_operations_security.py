import pytest

from qaos_common import CancellationToken, ProcessingLimits, ProgressEvent
from qaos_common.errors import ProcessCancelledError, QAOSCommonError


def test_limits_validate_relationships() -> None:
    with pytest.raises(ValueError):
        ProcessingLimits(max_rows=0)
    with pytest.raises(ValueError):
        ProcessingLimits(max_cell_bytes=300 * 1024 * 1024)
    with pytest.raises(ValueError):
        ProcessingLimits(max_image_bytes=100, max_cell_bytes=50)


def test_progress_contract() -> None:
    event = ProgressEvent("reading", 25, 100, "Reading row 25", 25)
    assert event.current == 25
    with pytest.raises(ValueError):
        ProgressEvent("unknown", 0)
    with pytest.raises(ValueError):
        ProgressEvent("reading", 2, 1)
    with pytest.raises(ValueError):
        ProgressEvent("reading", 0, row_number=0)


def test_cancellation_is_distinct() -> None:
    token = CancellationToken()
    assert not token.is_cancelled()
    token.raise_if_cancelled()
    token.cancel()
    with pytest.raises(ProcessCancelledError) as error:
        token.raise_if_cancelled()
    assert error.value.code == "PROCESS_CANCELLED"


def test_errors_recursively_redact_payloads() -> None:
    payload = "A" * 120
    error = QAOSCommonError(
        f"bad data:image/png;base64,{payload}", details={"raw": payload, "binary": b"secret"}
    )
    rendered = f"{error!s} {error.details!r}"
    assert payload not in rendered
    assert "redacted" in rendered
