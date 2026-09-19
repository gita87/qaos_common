"""Safe hand-off shape for multimedia_enhancement_task (no agent implementation)."""

from collections.abc import Iterator

from qaos_common.csvio import QAOSCSVReader
from qaos_common.rich_content import parse_cell
from qaos_common.schemas import validate_qaos_headers


def iter_safe_agent_inputs(path: str) -> Iterator[dict[str, object]]:
    with QAOSCSVReader(path) as reader:
        validate_qaos_headers(reader.headers)
        for row_number, row in reader:
            parsed = parse_cell(row["question_text"])
            if parsed.contains_image:
                continue
            yield {
                "row_number": row_number,
                "text": parsed.plain_text,
                "contains_existing_image": False,
            }
