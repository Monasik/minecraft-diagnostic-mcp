def parse_properties(text: str) -> dict:
    data: dict[str, str] = {}
    invalid_lines: list[int] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue

        separator_index = _find_separator(raw_line)
        if separator_index == -1:
            invalid_lines.append(line_number)
            continue

        key = raw_line[:separator_index].strip()
        value = raw_line[separator_index + 1 :].strip()
        if not key:
            invalid_lines.append(line_number)
            continue
        data[key] = value

    parse_error = None
    if invalid_lines:
        parse_error = "Invalid property syntax on lines: " + ", ".join(str(line) for line in invalid_lines)

    return {
        "parsed": True,
        "data": data,
        "parse_error": parse_error,
    }


def _find_separator(line: str) -> int:
    for separator in ("=", ":"):
        index = line.find(separator)
        if index != -1:
            return index
    return -1
