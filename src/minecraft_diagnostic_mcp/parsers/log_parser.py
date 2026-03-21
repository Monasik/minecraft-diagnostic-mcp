import re


LOG_START_RE = re.compile(r"^\s*(\[[^\]]+\]\s*)?(\[[A-Za-z0-9 _./:-]+\]\s*)+")
STACKTRACE_RE = re.compile(r"^\s+(at .+|\.{3} \d+ more|Suppressed: .+)$")
CAUSED_BY_RE = re.compile(r"^\s*Caused by:\s+.+$")
LEVEL_RE = re.compile(r"\[[^\]]*?\b(INFO|WARN|WARNING|ERROR)\]")


def parse_log_records(raw_text: str) -> list[dict]:
    if not raw_text.strip():
        return []

    records: list[dict] = []
    current_record: dict | None = None

    for index, line in enumerate(raw_text.splitlines(), start=1):
        if _starts_new_record(line):
            if current_record is not None:
                records.append(current_record)
            current_record = {
                "start_line": index,
                "lines": [line],
            }
            continue

        if current_record is None:
            current_record = {
                "start_line": index,
                "lines": [line],
            }
            continue

        if _is_stacktrace_line(line) or not line.strip():
            current_record["lines"].append(line)
        else:
            records.append(current_record)
            current_record = {
                "start_line": index,
                "lines": [line],
            }

    if current_record is not None:
        records.append(current_record)

    for record in records:
        joined_text = "\n".join(record["lines"])
        first_line = record["lines"][0] if record["lines"] else ""
        upper_text = joined_text.upper()
        record["text"] = joined_text
        record["level"] = _detect_level(first_line, upper_text)
        record["has_stacktrace"] = len(record["lines"]) > 1 and any(
            _is_stacktrace_line(line) for line in record["lines"][1:]
        )

    return records


def _starts_new_record(line: str) -> bool:
    return bool(LOG_START_RE.match(line))


def _is_stacktrace_line(line: str) -> bool:
    return bool(STACKTRACE_RE.match(line) or CAUSED_BY_RE.match(line))


def _detect_level(first_line: str, upper_text: str) -> str:
    upper_first_line = first_line.upper()
    level_match = LEVEL_RE.search(upper_first_line)
    if level_match:
        matched_level = level_match.group(1)
        if matched_level == "ERROR":
            return "ERROR"
        if matched_level in {"WARN", "WARNING"}:
            return "WARN"
        return "INFO"
    if not _starts_new_record(first_line):
        if "ERROR" in upper_text or "EXCEPTION" in upper_text:
            return "ERROR"
        if "WARN" in upper_text or "WARNING" in upper_text:
            return "WARN"
    return "INFO"
