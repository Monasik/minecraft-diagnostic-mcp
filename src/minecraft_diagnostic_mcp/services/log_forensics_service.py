from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
import gzip
from pathlib import Path
import re
from typing import Any, Iterator

from minecraft_diagnostic_mcp.collectors.filesystem_collector import get_logs_dir, list_log_files
from minecraft_diagnostic_mcp.services.plugin_service import list_plugins


MINECRAFT_TIME_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]")
LOG_FILE_DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
WATCHDOG_PATTERNS = (
    "watchdog thread",
    "server watchdog",
    "a single server tick took",
)
LAG_PATTERNS = ("can't keep up!",)
COMMAND_PATTERNS = (
    re.compile(r"issued server command:\s*(?P<command>.+)$", re.IGNORECASE),
    re.compile(r"\[(?P<player>[^\]]+)\]\s*/(?P<command>.+)$"),
)
STACKTRACE_FRAME_RE = re.compile(r"^\s+at\s+([A-Za-z0-9_$.]+)\(")


def list_log_sources(source: str = "all", date_value: str | None = None) -> dict[str, Any]:
    target_date = _parse_date(date_value)
    selected_files, notices = _select_log_files(source=source, target_date=target_date)

    sources = []
    for log_file in selected_files:
        metadata = _inspect_log_source(log_file["path"], target_date=target_date)
        sources.append(metadata)

    return {
        "source": source,
        "date": target_date.isoformat() if target_date else None,
        "source_count": len(sources),
        "sources": sources,
        "precision": {
            "guaranteed": all(item["time_range"]["guaranteed"] for item in sources) if sources else False,
            "notices": notices + [notice for item in sources for notice in item.get("precision_notices", [])],
        },
    }


def extract_raw_logs(
    source: str = "all",
    date_value: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    around: str | None = None,
    window_seconds: int = 120,
    contains: str | None = None,
    regex: str | None = None,
    case_sensitive: bool = False,
    before_lines: int = 0,
    after_lines: int = 0,
    max_lines: int = 400,
    mode: str = "full_raw",
) -> dict[str, Any]:
    filters = _build_filters(
        date_value=date_value,
        time_from=time_from,
        time_to=time_to,
        around=around,
        window_seconds=window_seconds,
        contains=contains,
        regex=regex,
        case_sensitive=case_sensitive,
    )
    selected_files, notices = _select_log_files(source=source, target_date=filters["target_date"])
    matches, search_meta = _collect_matching_records(
        selected_files=selected_files,
        filters=filters,
        max_lines=max_lines,
        before_lines=max(0, int(before_lines)),
        after_lines=max(0, int(after_lines)),
        mode=mode,
    )

    return {
        "source": source,
        "mode": _normalize_output_mode(mode),
        "filters": _serialize_filters(filters),
        "matched_record_count": len(matches),
        "matched_line_count": sum(item["line_count"] for item in matches),
        "truncated": search_meta["truncated"],
        "files_scanned": search_meta["files_scanned"],
        "records": matches,
        "precision": {
            "guaranteed": not search_meta["precision_notices"],
            "notices": notices + search_meta["precision_notices"],
        },
    }


def search_logs(
    source: str = "all",
    date_value: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    contains: str | None = None,
    regex: str | None = None,
    case_sensitive: bool = False,
    before_lines: int = 0,
    after_lines: int = 0,
    max_lines: int = 300,
    mode: str = "full",
) -> dict[str, Any]:
    return extract_raw_logs(
        source=source,
        date_value=date_value,
        time_from=time_from,
        time_to=time_to,
        contains=contains,
        regex=regex,
        case_sensitive=case_sensitive,
        before_lines=before_lines,
        after_lines=after_lines,
        max_lines=max_lines,
        mode=mode,
    )


def incident_timeline(
    source: str = "all",
    date_value: str | None = None,
    around: str | None = None,
    window_seconds: int = 120,
    before_minutes: int = 10,
    after_minutes: int = 5,
    max_lines: int = 600,
    mode: str = "full",
) -> dict[str, Any]:
    filters = _build_filters(
        date_value=date_value,
        around=around,
        window_seconds=window_seconds,
    )
    target_date = filters["target_date"]
    selected_files, notices = _select_log_files(source=source, target_date=target_date)
    before_delta = timedelta(minutes=max(0, int(before_minutes)))
    after_delta = timedelta(minutes=max(0, int(after_minutes)))
    incident_records, meta = _collect_matching_records(
        selected_files=selected_files,
        filters=filters,
        max_lines=max_lines,
        before_lines=0,
        after_lines=0,
        mode=mode,
    )

    anchor_record = incident_records[0] if incident_records else None
    anchor_dt = _record_timestamp(anchor_record) if anchor_record else filters.get("around_datetime")

    if anchor_dt is None:
        return {
            "source": source,
            "filters": _serialize_filters(filters),
            "incident_found": False,
            "message": "No precise incident anchor could be determined from the requested filters.",
            "precision": {
                "guaranteed": False,
                "notices": notices + meta["precision_notices"] + ["Incident timeline requires a resolvable date and timestamp."],
            },
            "records": [],
        }

    timeline_filters = _build_filters(
        date_value=anchor_dt.date().isoformat(),
        time_from=(anchor_dt - before_delta).time().isoformat(timespec="seconds"),
        time_to=(anchor_dt + after_delta).time().isoformat(timespec="seconds"),
    )
    timeline_records, timeline_meta = _collect_matching_records(
        selected_files=selected_files,
        filters=timeline_filters,
        max_lines=max_lines,
        before_lines=0,
        after_lines=0,
        mode=mode,
    )

    preceding_player_actions = _extract_player_actions(
        timeline_records,
        upper_bound=anchor_dt,
        lower_bound=anchor_dt - before_delta,
    )
    relevant_stacktraces = [
        item for item in timeline_records
        if item.get("has_stacktrace") or _record_matches_keywords(item, WATCHDOG_PATTERNS)
    ]
    following_recovery_events = [
        item for item in timeline_records
        if _record_timestamp(item) and _record_timestamp(item) > anchor_dt and _is_recovery_event(item)
    ]

    return {
        "source": source,
        "incident_found": True,
        "incident_timestamp": anchor_dt.isoformat(sep=" "),
        "filters": {
            **_serialize_filters(filters),
            "before_minutes": max(0, int(before_minutes)),
            "after_minutes": max(0, int(after_minutes)),
        },
        "anchor_record": anchor_record,
        "preceding_player_actions": preceding_player_actions,
        "relevant_plugin_stacktraces": relevant_stacktraces[:20],
        "following_recovery_events": following_recovery_events[:20],
        "records": timeline_records,
        "precision": {
            "guaranteed": not (meta["precision_notices"] or timeline_meta["precision_notices"]),
            "notices": notices + meta["precision_notices"] + timeline_meta["precision_notices"],
        },
    }


def list_cant_keep_up_events(source: str = "archives", date_value: str | None = None, max_lines: int = 200) -> dict[str, Any]:
    return search_logs(
        source=source,
        date_value=date_value,
        contains="Can't keep up!",
        case_sensitive=False,
        max_lines=max_lines,
        mode="full",
    )


def list_watchdog_dumps(source: str = "archives", date_value: str | None = None, max_lines: int = 600, mode: str = "full_raw") -> dict[str, Any]:
    return search_logs(
        source=source,
        date_value=date_value,
        regex="Watchdog Thread|Server Watchdog|A single server tick took",
        case_sensitive=False,
        max_lines=max_lines,
        mode=mode,
    )


def list_stacktrace_plugins(source: str = "all", date_value: str | None = None) -> dict[str, Any]:
    filters = _build_filters(date_value=date_value)
    selected_files, notices = _select_log_files(source=source, target_date=filters["target_date"])
    plugin_inventory = {
        str(plugin.get("name", "")).casefold(): str(plugin.get("name", ""))
        for plugin in list_plugins().get("plugins", [])
        if plugin.get("name")
    }

    counts: Counter[str] = Counter()
    files_scanned: list[str] = []
    precision_notices: list[str] = []
    for file_info in selected_files:
        files_scanned.append(file_info["path"])
        for record in _iter_log_records(Path(file_info["path"]), explicit_date=filters["target_date"]):
            if not record["has_stacktrace"]:
                continue
            for plugin_name in _extract_stacktrace_plugins(record["text"], plugin_inventory):
                counts[plugin_name] += 1
            precision_notices.extend(record["precision_notices"])

    return {
        "source": source,
        "date": filters["target_date"].isoformat() if filters["target_date"] else None,
        "plugin_count": len(counts),
        "plugins": [{"plugin": name, "occurrences": count} for name, count in counts.most_common()],
        "files_scanned": files_scanned,
        "precision": {
            "guaranteed": not (notices or precision_notices),
            "notices": notices + precision_notices,
        },
    }


def list_player_commands(
    source: str = "all",
    date_value: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    around: str | None = None,
    before_minutes: int = 10,
    max_lines: int = 200,
) -> dict[str, Any]:
    filters = _build_filters(
        date_value=date_value,
        time_from=time_from,
        time_to=time_to,
        around=around,
        window_seconds=max(60, int(before_minutes) * 60),
    )
    if filters.get("around_datetime") is not None and time_from is None and time_to is None:
        anchor = filters["around_datetime"]
        filters["time_from"] = (anchor - timedelta(minutes=max(0, int(before_minutes)))).time()
        filters["time_to"] = anchor.time()

    selected_files, notices = _select_log_files(source=source, target_date=filters["target_date"])
    matches, meta = _collect_matching_records(
        selected_files=selected_files,
        filters=filters,
        max_lines=max_lines,
        before_lines=0,
        after_lines=0,
        mode="full",
        predicate=_record_has_player_command,
    )

    commands = []
    for item in matches:
        command_info = _extract_command_info(item["text"])
        commands.append(
            {
                "timestamp": item.get("timestamp"),
                "player": command_info.get("player"),
                "command": command_info.get("command"),
                "source": item["source"],
                "text": item["text"],
            }
        )

    return {
        "source": source,
        "filters": _serialize_filters(filters),
        "command_count": len(commands),
        "commands": commands,
        "precision": {
            "guaranteed": not (notices or meta["precision_notices"]),
            "notices": notices + meta["precision_notices"],
        },
    }


def _build_filters(
    date_value: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    around: str | None = None,
    window_seconds: int = 120,
    contains: str | None = None,
    regex: str | None = None,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    target_date = _parse_date(date_value)
    parsed_time_from = _parse_time(time_from)
    parsed_time_to = _parse_time(time_to)
    around_time = _parse_time(around)
    around_datetime = None
    if target_date and around_time:
        around_datetime = datetime.combine(target_date, around_time)

    compiled_regex = None
    if regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled_regex = re.compile(regex, flags)

    return {
        "target_date": target_date,
        "time_from": parsed_time_from,
        "time_to": parsed_time_to,
        "around_time": around_time,
        "around_datetime": around_datetime,
        "window_seconds": max(1, int(window_seconds)),
        "contains": contains,
        "regex": regex,
        "compiled_regex": compiled_regex,
        "case_sensitive": bool(case_sensitive),
    }


def _serialize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": filters["target_date"].isoformat() if filters.get("target_date") else None,
        "time_from": filters["time_from"].isoformat() if filters.get("time_from") else None,
        "time_to": filters["time_to"].isoformat() if filters.get("time_to") else None,
        "around": filters["around_time"].isoformat() if filters.get("around_time") else None,
        "window_seconds": filters.get("window_seconds"),
        "contains": filters.get("contains"),
        "regex": filters.get("regex"),
        "case_sensitive": filters.get("case_sensitive", False),
    }


def _normalize_output_mode(mode: str) -> str:
    normalized = str(mode or "full_raw").strip().lower()
    if normalized not in {"summary", "full", "full_raw"}:
        return "full_raw"
    return normalized


def _select_log_files(source: str, target_date: date | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    logs_dir = get_logs_dir()
    available = []
    latest_path = logs_dir / "latest.log"
    notices: list[str] = []

    for log_file in list_log_files():
        path = Path(log_file.path)
        source_kind = _classify_source_kind(path)
        inferred_date, date_source = _infer_file_date(path, target_date=None, modified_time=log_file.modified_time)
        available.append(
            {
                "path": str(path),
                "name": path.name,
                "file_type": log_file.file_type,
                "source_kind": source_kind,
                "inferred_date": inferred_date,
                "date_source": date_source,
            }
        )

    normalized_source = str(source or "all").strip()
    filtered = []
    if normalized_source == "latest":
        filtered = [item for item in available if Path(item["path"]) == latest_path]
    elif normalized_source == "archives":
        filtered = [item for item in available if item["source_kind"] == "archive_log"]
    elif normalized_source.startswith("file:"):
        expected_name = normalized_source.split(":", 1)[1].strip()
        filtered = [item for item in available if item["name"] == expected_name or item["path"] == expected_name]
        if not filtered:
            notices.append(f"No log file matched explicit selector '{expected_name}'.")
    else:
        filtered = available

    if target_date is not None:
        filtered = [item for item in filtered if item["inferred_date"] == target_date]
        if normalized_source == "all":
            notices.append(
                f"Applied exact date filter {target_date.isoformat()}; files from other dates, including today's latest.log, were excluded."
            )

    return sorted(filtered, key=lambda item: (item["name"] != "latest.log", item["name"])), notices


def _inspect_log_source(path_str: str, target_date: date | None = None) -> dict[str, Any]:
    path = Path(path_str)
    inferred_date, date_source = _infer_file_date(path, target_date=target_date)
    first_timestamp = None
    last_timestamp = None
    line_count = 0
    for line_count, line in enumerate(_iter_file_lines(path), start=1):
        parsed = _parse_line_time(line)
        if parsed is None:
            continue
        if first_timestamp is None:
            first_timestamp = parsed
        last_timestamp = parsed

    guaranteed = bool(inferred_date and first_timestamp and last_timestamp and date_source != "mtime_inferred")
    time_range = {
        "date": inferred_date.isoformat() if inferred_date else None,
        "first_time": first_timestamp.isoformat() if first_timestamp else None,
        "last_time": last_timestamp.isoformat() if last_timestamp else None,
        "guaranteed": guaranteed,
        "date_source": date_source,
    }
    precision_notices = []
    if path.name == "latest.log" and date_source == "mtime_inferred":
        precision_notices.append(
            "latest.log date was inferred from file modification time; cross-midnight precision cannot be fully guaranteed without an explicit date filter."
        )

    return {
        "name": path.name,
        "path": str(path),
        "source_kind": _classify_source_kind(path),
        "file_type": "log.gz" if path.suffix.lower() == ".gz" else "log",
        "line_count": line_count,
        "time_range": time_range,
        "precision_notices": precision_notices,
    }


def _collect_matching_records(
    selected_files: list[dict[str, Any]],
    filters: dict[str, Any],
    max_lines: int,
    before_lines: int,
    after_lines: int,
    mode: str,
    predicate=None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_mode = _normalize_output_mode(mode)
    matches = []
    precision_notices: list[str] = []
    files_scanned = []
    total_lines = 0
    truncated = False

    for file_info in selected_files:
        path = Path(file_info["path"])
        files_scanned.append({
            "path": str(path),
            "source_kind": file_info["source_kind"],
            "date": file_info["inferred_date"].isoformat() if file_info["inferred_date"] else None,
        })
        for record in _iter_log_records(path, explicit_date=filters["target_date"]):
            precision_notices.extend(record["precision_notices"])
            if not _record_matches_filters(record, filters):
                continue
            if predicate and not predicate(record):
                continue

            context_lines = _read_line_window(path, record["line_start"] - before_lines, record["line_end"] + after_lines)
            entry = _format_record_entry(record, context_lines, normalized_mode)
            entry_line_count = entry["line_count"]
            if matches and total_lines + entry_line_count > max(1, int(max_lines)):
                truncated = True
                break
            matches.append(entry)
            total_lines += entry_line_count

        if truncated:
            break

    if _should_focus_nearest_record(filters, predicate) and matches:
        anchor = filters["around_datetime"]
        nearest = min(
            matches,
            key=lambda item: abs((_record_timestamp(item) - anchor).total_seconds()) if _record_timestamp(item) else float("inf"),
        )
        matches = [nearest]
        total_lines = nearest["line_count"]

    return matches, {
        "truncated": truncated,
        "files_scanned": files_scanned,
        "precision_notices": _unique_list(precision_notices),
    }


def _iter_log_records(path: Path, explicit_date: date | None = None) -> Iterator[dict[str, Any]]:
    inferred_date, date_source = _infer_file_date(path, target_date=explicit_date)
    current: dict[str, Any] | None = None
    precision_notices: list[str] = []
    if path.name == "latest.log" and date_source == "mtime_inferred" and explicit_date is None:
        precision_notices.append(
            "latest.log record timestamps use a date inferred from file modification time; use an explicit date to guarantee exact-day filtering."
        )

    for line_number, line in enumerate(_iter_file_lines(path), start=1):
        if _starts_new_record(line):
            if current is not None:
                yield _finalize_record(current, inferred_date, date_source, precision_notices)
            current = {"path": str(path), "line_start": line_number, "raw_lines": [line]}
            continue

        if current is None:
            current = {"path": str(path), "line_start": line_number, "raw_lines": [line]}
            continue

        if _is_stacktrace_line(line) or not line.strip():
            current["raw_lines"].append(line)
            continue

        yield _finalize_record(current, inferred_date, date_source, precision_notices)
        current = {"path": str(path), "line_start": line_number, "raw_lines": [line]}

    if current is not None:
        yield _finalize_record(current, inferred_date, date_source, precision_notices)


def _finalize_record(current: dict[str, Any], inferred_date: date | None, date_source: str, precision_notices: list[str]) -> dict[str, Any]:
    raw_lines = list(current["raw_lines"])
    text = "\n".join(raw_lines)
    line_time = _parse_line_time(raw_lines[0]) if raw_lines else None
    record_datetime = datetime.combine(inferred_date, line_time) if inferred_date and line_time else None
    return {
        "path": current["path"],
        "text": text,
        "raw_lines": raw_lines,
        "line_start": current["line_start"],
        "line_end": current["line_start"] + max(len(raw_lines) - 1, 0),
        "line_time": line_time,
        "timestamp": record_datetime,
        "date": inferred_date,
        "date_source": date_source,
        "has_stacktrace": any(_is_stacktrace_line(line) for line in raw_lines[1:]),
        "precision_notices": list(precision_notices),
    }


def _format_record_entry(record: dict[str, Any], context_lines: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    timestamp = record["timestamp"]
    source_path = record.get("path")
    entry = {
        "timestamp": timestamp.isoformat(sep=" ") if timestamp else None,
        "time": record["line_time"].isoformat() if record["line_time"] else None,
        "date": record["date"].isoformat() if record["date"] else None,
        "has_stacktrace": record["has_stacktrace"],
        "line_count": len(context_lines),
        "source": {
            "path": str(record["path"]),
            "name": Path(record["path"]).name,
            "source_kind": _classify_source_kind(Path(record["path"])),
            "line_start": context_lines[0]["line_number"] if context_lines else record["line_start"],
            "line_end": context_lines[-1]["line_number"] if context_lines else record["line_end"],
            "record_line_start": record["line_start"],
            "record_line_end": record["line_end"],
            "date_source": record["date_source"],
        },
    }

    if mode == "summary":
        entry["summary"] = record["raw_lines"][0] if record["raw_lines"] else ""
        entry["matching_text"] = record["text"][:1200]
    elif mode == "full":
        entry["text"] = record["text"]
        entry["context_lines"] = context_lines
    else:
        entry["text"] = record["text"]
        entry["raw_lines"] = context_lines
        entry["full_raw"] = "\n".join(item["text"] for item in context_lines)

    return entry


def _record_matches_filters(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    target_date = filters.get("target_date")
    if target_date and record.get("date") != target_date:
        return False

    line_time = record.get("line_time")
    if filters.get("around_datetime") is not None:
        record_dt = record.get("timestamp")
        if record_dt is None:
            return False
        delta = abs((record_dt - filters["around_datetime"]).total_seconds())
        if delta > filters["window_seconds"]:
            return False
    else:
        if filters.get("time_from") and (line_time is None or line_time < filters["time_from"]):
            return False
        if filters.get("time_to") and (line_time is None or line_time > filters["time_to"]):
            return False

    contains = filters.get("contains")
    if contains:
        haystack = record["text"] if filters.get("case_sensitive") else record["text"].casefold()
        needle = contains if filters.get("case_sensitive") else contains.casefold()
        if needle not in haystack:
            return False

    compiled_regex = filters.get("compiled_regex")
    if compiled_regex and not compiled_regex.search(record["text"]):
        return False

    return True


def _record_timestamp(record: dict[str, Any] | None) -> datetime | None:
    if not record:
        return None
    value = record.get("timestamp")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _record_matches_keywords(record: dict[str, Any], keywords: tuple[str, ...]) -> bool:
    text = str(record.get("text", "")).casefold()
    return any(keyword in text for keyword in keywords)


def _extract_player_actions(records: list[dict[str, Any]], upper_bound: datetime, lower_bound: datetime) -> list[dict[str, Any]]:
    actions = []
    for item in records:
        record_dt = _record_timestamp(item)
        if record_dt is None or record_dt < lower_bound or record_dt > upper_bound:
            continue
        if not _record_has_player_command(item):
            continue
        info = _extract_command_info(item["text"])
        actions.append(
            {
                "timestamp": item.get("timestamp"),
                "player": info.get("player"),
                "command": info.get("command"),
                "source": item.get("source"),
                "text": item.get("text"),
            }
        )
    return actions


def _record_has_player_command(record: dict[str, Any]) -> bool:
    return _extract_command_info(record.get("text", "")).get("command") is not None


def _extract_command_info(text: str) -> dict[str, str | None]:
    for pattern in COMMAND_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        command = match.groupdict().get("command")
        if command and not command.startswith("/"):
            command = "/" + command
        return {
            "player": match.groupdict().get("player"),
            "command": command,
        }
    return {"player": None, "command": None}


def _extract_stacktrace_plugins(text: str, plugin_inventory: dict[str, str]) -> list[str]:
    found = []
    lowered = text.casefold()
    for plugin_key, plugin_name in plugin_inventory.items():
        if plugin_key and plugin_key in lowered and plugin_name not in found:
            found.append(plugin_name)

    for frame in STACKTRACE_FRAME_RE.findall(text):
        tail = frame.split(".")[0]
        if tail and tail not in found and len(tail) > 2:
            found.append(tail)

    return found


def _is_recovery_event(record: dict[str, Any]) -> bool:
    text = str(record.get("text", "")).casefold()
    return any(
        marker in text for marker in (
            'for help, type "help"',
            "starting minecraft server",
            "done (",
            "saving players",
            "stopping server",
            "server thread/info",
        )
    )


def _infer_file_date(path: Path, target_date: date | None = None, modified_time=None) -> tuple[date | None, str]:
    if target_date is not None:
        return target_date, "explicit_filter"

    match = LOG_FILE_DATE_RE.search(path.name)
    if match:
        return datetime.strptime(match.group("date"), "%Y-%m-%d").date(), "filename"

    if modified_time is not None:
        return modified_time.date(), "mtime_inferred"

    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date(), "mtime_inferred"
    except OSError:
        return None, "unknown"


def _classify_source_kind(path: Path) -> str:
    name = path.name.lower()
    if name == "latest.log":
        return "latest_log"
    if name.endswith(".log.gz") or path.suffix.lower() == ".gz":
        return "archive_log"
    return "workspace_log"


def _iter_file_lines(path: Path) -> Iterator[str]:
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            yield line.rstrip("\n")


def _read_line_window(path: Path, start_line: int, end_line: int) -> list[dict[str, Any]]:
    start = max(1, int(start_line))
    end = max(start, int(end_line))
    output = []
    for line_number, line in enumerate(_iter_file_lines(path), start=1):
        if line_number < start:
            continue
        if line_number > end:
            break
        output.append({"line_number": line_number, "text": line})
    return output


def _starts_new_record(line: str) -> bool:
    return bool(MINECRAFT_TIME_RE.match(line))


def _is_stacktrace_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("at ") or stripped.startswith("Caused by:") or stripped.startswith("... ") or stripped.startswith("Suppressed:")


def _parse_line_time(line: str) -> time | None:
    match = MINECRAFT_TIME_RE.match(line)
    if not match:
        return None
    return time(hour=int(match.group(1)), minute=int(match.group(2)), second=int(match.group(3)))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    normalized = value.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(normalized, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format '{value}'. Expected HH:MM or HH:MM:SS.")


def _unique_list(values: list[str]) -> list[str]:
    unique = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return unique


def _should_focus_nearest_record(filters: dict[str, Any], predicate) -> bool:
    return bool(
        filters.get("around_datetime") is not None
        and predicate is None
        and not filters.get("contains")
        and not filters.get("regex")
        and filters.get("time_from") is None
        and filters.get("time_to") is None
    )
