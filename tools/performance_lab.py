"""Bounded, app-scoped Performance Lab collection, profile selection and analysis.

Only the explicit ``profile`` subcommand writes to the phone. Collect never
changes phone files; analyze works offline and never imports device libraries.
Performance Lab 1.0.15 defaults to profile "all" when its profile file is absent;
invalid file contents fall back to baseline. This helper never writes a default.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

PROFILES = ("baseline", "retry", "clear-cache", "limiter", "all",
            "all-no-retry", "all-no-clear-cache", "all-no-limiter")
REMOTE_LOGS = "/Documents/PerformanceLab"
REMOTE_PROFILE = "/Documents/performance-profile.txt"
MAX_LOG_BYTES = 8 * 1024 * 1024
MAX_LOGS = 12
SETTINGS = ("resolution", "fps_limit", "aa", "transparency_aa",
            "shadow_resolution", "gi_filter", "motion_blur")
FRAME_KIND = "IOS-EXPERIMENT-FRAME"
RETRY_KIND = "IOS-RETRY-SNAPSHOT"
BACKEND_KIND = "IOS-METAL-COUNTERS"
BACKEND_COUNTERS = ("partial_color", "partial_color_depth", "cache_uses", "state_created",
                    "state_released", "full_color", "partial_depth", "full_depth",
                    "command_commits", "acquire_commits", "present_commits", "wait_commits",
                    "render_encoders", "residency_adds", "residency_removes", "residency_commits",
                    "create_samples", "create_sample_ns")
LINE = re.compile(r"IOS-LAB v1 (?P<prefix>.*?) (?P<kind>IOS-[A-Z0-9-]+) v1 (?P<body>.*)$")
KV = re.compile(r"(?:^|\s)([A-Za-z0-9_]+)=([^\s]+)")
LOG_NAME = re.compile(r"session-[A-Za-z0-9_-]+\.log\Z")


def device_service(bundle_id: str, udid: str | None = None):
    # Lazy: offline analysis/unit tests do not need pymobiledevice3.
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService
    lockdown = create_using_usbmux(serial=udid) if udid else create_using_usbmux()
    return HouseArrestService(lockdown, bundle_id, documents_only=True)


def select_profile(service, name: str) -> dict[str, Any]:
    if name not in PROFILES:
        raise ValueError("Unsupported performance profile")
    data = (name + "\n").encode("ascii")
    # This is deliberately the only phone-write call in this tool.
    service.set_file_contents(REMOTE_PROFILE, data)
    if service.get_file_contents(REMOTE_PROFILE) != data:
        raise RuntimeError("Profile read-back does not match; do not launch a test")
    return {"profile": name, "phone_file": REMOTE_PROFILE,
            "restart_required": True, "note": "Verify the startup log before testing."}


def collect(service, output_root: Path) -> dict[str, Any]:
    candidates, skipped = [], []
    for name in service.listdir(REMOTE_LOGS):
        if not LOG_NAME.fullmatch(name):
            continue
        remote = REMOTE_LOGS + "/" + name
        stat = service.stat(remote)
        size = int(stat["st_size"])
        if stat.get("st_ifmt") != "S_IFREG" or not 0 <= size <= MAX_LOG_BYTES:
            skipped.append({"file": name, "reason": "not_regular_or_oversized"})
            continue
        modified = stat.get("st_mtime", 0)
        modified = modified.timestamp() if hasattr(modified, "timestamp") else float(modified)
        candidates.append((modified, name, size))
    chosen = sorted(candidates, reverse=True)[:MAX_LOGS]
    output = output_root.resolve() / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    output.mkdir(parents=True, exist_ok=False)
    copied = []
    for _, name, size in chosen:
        handle = service.fopen(REMOTE_LOGS + "/" + name, "r")
        try:
            # Capture only the size observed above, even if a live log grows.
            data = service.fread(handle, size) if size else b""
        finally:
            service.fclose(handle)
        if len(data) > MAX_LOG_BYTES or len(data) > size:
            raise RuntimeError("Device returned more than the bounded log snapshot")
        with (output / name).open("xb") as stream:
            stream.write(data)
        copied.append({"file": name, "bytes": len(data), "observed_bytes": size,
                       "sha256": hashlib.sha256(data).hexdigest(),
                       "complete_final_line": not data or data.endswith(b"\n")})
    result = {"output": str(output), "copied": copied, "skipped": skipped,
              "read_only_phone": True, "note": "Active logs are bounded snapshots; incomplete final lines are ignored."}
    (output / "collection.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def is_true(value: Any) -> bool:
    return str(value).lower() in ("true", "1")


def is_false(value: Any) -> bool:
    return str(value).lower() in ("false", "0")


def parse_record(line: str) -> dict[str, Any] | None:
    match = LINE.search(line.strip())
    if not match:
        return None
    prefix = dict(KV.findall(match["prefix"]))
    data = dict(KV.findall(match["body"]))
    if not all(key in prefix for key in ("build", "session", "profile", "monotonic_ms", "stage")):
        return None
    timestamp = number(prefix["monotonic_ms"])
    if timestamp is None or timestamp < 0:
        return None
    return {"prefix": prefix, "data": data, "kind": match["kind"], "time": timestamp}


def context_reasons(record: dict[str, Any]) -> list[str]:
    prefix = record["prefix"]
    reasons = []
    if prefix["profile"] not in PROFILES:
        reasons.append("unknown_profile")
    stage = prefix["stage"].lower()
    if stage in ("unknown", "none", "null", "", "-", "0"):
        reasons.append("unknown_stage")
    elif any(word in stage for word in ("menu", "title", "worldmap", "world_map", "stage_select", "selector")):
        reasons.append("menu")
    for key in ("paused", "loading", "suspended"):
        if is_true(prefix.get(key)):
            reasons.append(key)
        elif not is_false(prefix.get(key)):
            reasons.append("unknown_" + key)
    return reasons


def frame_reasons(record: dict[str, Any]) -> list[str]:
    reasons = context_reasons(record)
    if record.get("configuration_invalid"):
        reasons.append("invalid_or_conflicting_configuration")
    data = record["data"]
    for key in ("mixed_stage", "loading_seen", "paused_seen"):
        if is_true(data.get(key)):
            reasons.append(key)
        elif not is_false(data.get(key)):
            reasons.append("unknown_" + key)
    if not is_true(data.get("memory_valid")):
        reasons.append("memory_invalid")
    if data.get("epoch_start") is None or data.get("epoch_start") != data.get("epoch_end"):
        reasons.append("epoch_transition")
    if data.get("thermal") not in ("0", "1", "2", "3", "nominal", "normal", "fair", "serious", "critical"):
        reasons.append("unknown_thermal")
    for key in SETTINGS:
        if key not in data or data[key].lower() in ("unknown", "nan", "none", "null") and key not in ("aa",):
            reasons.append("missing_setting_" + key)
    for key in ("frames", "elapsed_s", "frame_p95_ms", "frame_max_ms", "footprint_bytes"):
        val = number(data.get(key))
        if val is None or val < 0 or (key in ("frames", "elapsed_s") and val == 0):
            reasons.append("invalid_" + key)
    frames = number(data.get("frames"))
    if frames is not None and frames != int(frames):
        reasons.append("noninteger_frames")
    return reasons


def group_key(record: dict[str, Any]) -> tuple[str, ...]:
    prefix, data = record["prefix"], record["data"]
    return (prefix["build"], prefix["profile"], prefix["stage"],
            *(data[key] for key in SETTINGS), data["thermal"],
            record["source_sha"], record["bundle_version"])


def summarize(lines: list[str]) -> dict[str, Any]:
    records, identities, conflicting = [], {}, set()
    duplicates, malformed = 0, 0
    for line in lines:
        record = parse_record(line)
        if record is None:
            malformed += bool(line.strip())
            continue
        prefix = record["prefix"]
        identity = (prefix["build"], prefix["session"], record["kind"], record["time"])
        if identity in identities:
            if record == identities[identity]:
                duplicates += 1
            else:
                conflicting.add(identity)
            continue
        record["identity"] = identity
        identities[identity] = record.copy()
        # Do not include analysis-only identity in duplicate equality.
        identities[identity].pop("identity", None)
        records.append(record)
    sessions = defaultdict(list)
    for record in records:
        sessions[(record["prefix"]["build"], record["prefix"]["session"])].append(record)
    groups, excluded = defaultdict(list), Counter()
    session_metadata = []
    frame_by_session = {}
    for session, events in sessions.items():
        events.sort(key=lambda record: record["time"])
        configs = [event for event in events if event["kind"] == "IOS-LAB-CONFIG"]
        unique_configs = {json.dumps(event["data"], sort_keys=True) for event in configs}
        config = configs[0]["data"] if configs else {}
        configuration_invalid = bool(configs) and (len(unique_configs) != 1 or not is_true(config.get("valid")))
        # Missing source identity must not silently pool separate builds that
        # happen to use the same human-facing version string.
        source = config.get("source", "unknown")
        if source in ("unknown", "", "null"):
            source = "unverified-session-" + session[1]
        version = config.get("bundle_version", "unknown")
        session_metadata.append({"build": session[0], "session": session[1],
                                 "source_sha": source, "bundle_version": version,
                                 "configuration": config, "configuration_invalid": configuration_invalid})
        for event in events:
            event.update(source_sha=source, bundle_version=version, configuration_invalid=configuration_invalid)
        frames = []
        for frame in (r for r in events if r["kind"] == FRAME_KIND):
            reasons = frame_reasons(frame)
            if frame["identity"] in conflicting:
                reasons.append("conflicting_duplicate")
            elapsed = number(frame["data"].get("elapsed_s")) or 0
            start, end = frame["time"] - elapsed * 1000, frame["time"]
            for event in events:
                if start < event["time"] <= end:
                    if context_reasons(event):
                        reasons.append("context_transition_in_window")
                    if event["prefix"]["stage"] != frame["prefix"]["stage"] or event["prefix"]["profile"] != frame["prefix"]["profile"]:
                        reasons.append("stage_or_profile_transition_in_window")
            frame["accepted"] = not reasons
            frame["group"] = group_key(frame) if not reasons else None
            frame["start"] = start
            frames.append(frame)
            if reasons:
                excluded.update(set(reasons))
            else:
                groups[frame["group"]].append(frame)
        frame_by_session[session] = frames

    # Deltas only across adjacent valid windows in one launch and same group.
    # Never bridge a paused/loading/thermal-transition or missing-frame gap.
    delta_groups = defaultdict(lambda: defaultdict(lambda: {"delta": 0.0, "elapsed_s": 0.0, "intervals": 0}))
    for session, events in sessions.items():
        frames = frame_by_session[session]
        for kind in (FRAME_KIND, RETRY_KIND, BACKEND_KIND):
            previous = None
            for record in (r for r in events if r["kind"] == kind):
                if kind == FRAME_KIND:
                    frame = record
                else:
                    near = [f for f in frames if abs(f["time"] - record["time"]) <= 250]
                    frame = min(near, key=lambda f: abs(f["time"] - record["time"])) if near else None
                valid = (frame is not None and frame["accepted"] and
                         record["identity"] not in conflicting and not context_reasons(record))
                if kind == RETRY_KIND:
                    valid = valid and is_true(record["data"].get("snapshot_valid"))
                current = (record, frame) if valid else None
                if current and previous:
                    old, old_frame = previous
                    seconds = (record["time"] - old["time"]) / 1000.0
                    continuous = (seconds > 0 and frame["group"] == old_frame["group"] and
                                  abs(frame["start"] - old_frame["time"]) <= 250)
                    if continuous:
                        if kind == FRAME_KIND:
                            fields = {"process_cpu_ms": "process_cpu_valid", "present_thread_cpu_ms": "present_thread_cpu_valid",
                                      "limiter_sleep_ms": None, "limiter_yield_ms": None,
                                      "limiter_wait_frames": None, "limiter_overshoot_ms": None}
                        elif kind == RETRY_KIND:
                            fields = {"passes": None, "stalled": None, "backoffs": None, "thread_cpu_ms": "cpu_valid"}
                        else:
                            fields = {key: None for key in BACKEND_COUNTERS}
                        for key, validity in fields.items():
                            if validity and not all(is_true(r["data"].get(validity)) for r in (old, record)):
                                continue
                            if kind == RETRY_KIND and key == "thread_cpu_ms":
                                ages = [number(r["data"].get("sample_age_ms")) for r in (old, record)]
                                if any(age is None or age < 0 or age > seconds * 1000 for age in ages):
                                    continue  # Stale sampled CPU is not proof of zero CPU use.
                            first, last = number(old["data"].get(key)), number(record["data"].get(key))
                            if first is None or last is None or last < first:
                                continue
                            item = delta_groups[frame["group"]][kind + "." + key]
                            item["delta"] += last - first
                            item["elapsed_s"] += seconds
                            item["intervals"] += 1
                previous = current

    result_groups = []
    for key, frames in sorted(groups.items()):
        durations = [float(f["data"]["elapsed_s"]) for f in frames]
        total_seconds = sum(durations)
        frame_count = sum(int(f["data"]["frames"]) for f in frames)
        p95 = [float(f["data"]["frame_p95_ms"]) for f in frames]
        result = {"build": key[0], "profile": key[1], "stage": key[2],
                  "settings": dict(zip(SETTINGS, key[3:3 + len(SETTINGS)])),
                  "thermal": key[3 + len(SETTINGS)], "source_sha": key[-2], "bundle_version": key[-1],
                  "sessions": sorted({f["prefix"]["session"] for f in frames}),
                  "windows": len(frames), "frames": frame_count, "elapsed_s": total_seconds,
                  "weighted_fps": frame_count / total_seconds,
                  "window_p95_ms": {"min": min(p95), "max": max(p95),
                                    "note": "Range of per-window p95 values; NOT a pooled frame p95."},
                  "frame_max_ms": max(float(f["data"]["frame_max_ms"]) for f in frames),
                  "footprint_bytes_range": [min(float(f["data"]["footprint_bytes"]) for f in frames), max(float(f["data"]["footprint_bytes"]) for f in frames)],
                  "cumulative_deltas": {}}
        for metric, delta in sorted(delta_groups[key].items()):
            result["cumulative_deltas"][metric] = {**delta, "per_second": delta["delta"] / delta["elapsed_s"]}
        for metric in ("over33ms", "over50ms", "over1000ms"):
            values = [number(f["data"].get(metric)) for f in frames]
            if all(value is not None and value >= 0 for value in values):
                result[metric] = sum(values)
        gpu = [number(f["data"].get("gpu_timestamp_ms")) for f in frames]
        valid_gpu = [value for value in gpu if value is not None and value >= 0]
        if valid_gpu:
            result["async_gpu_timestamp_ms_range"] = [min(valid_gpu), max(valid_gpu)]
        result_groups.append(result)
    return {"schema": "performance-lab-analysis-v1", "parsed_records": len(records),
            "duplicate_records_ignored": duplicates, "conflicting_record_keys": len(conflicting),
            "unparsed_lines": malformed, "sessions": len(sessions),
            "session_metadata": session_metadata,
            "accepted_windows": sum(len(v) for v in groups.values()),
            "excluded_windows": sum(1 for frames in frame_by_session.values() for f in frames if not f["accepted"]),
            "excluded_reasons": dict(excluded), "groups": result_groups,
            "limitations": ["Observational comparisons do not establish causality or matched route/temperature.",
                            "CPU counters are elapsed CPU time, not exclusive per-pass CPU costs.",
                            "GPU timestamps are asynchronous samples and may refer to adjacent frames.",
                            "Thermal is categorical pressure, not a temperature measurement.",
                            "Window percentiles are not pooled; delta intervals exclude gaps and transitions."]}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("collect", "profile"):
        command = commands.add_parser(name)
        command.add_argument("--bundle-id", required=True)
        command.add_argument("--udid")
        if name == "collect":
            command.add_argument("--output-root", required=True, type=Path)
        else:
            command.add_argument("--name", choices=PROFILES, required=True,
                                 help="Explicitly write this profile for the next app launch; requires user authorization.")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("logs", nargs="+", type=Path)
    analyze.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "analyze":
        lines = []
        incomplete = 0
        for path in args.logs:
            if path.stat().st_size > MAX_LOG_BYTES:
                raise ValueError(f"Refusing oversized log: {path}")
            data = path.read_text(encoding="utf-8", errors="replace")
            pieces = data.splitlines(keepends=True)
            if pieces and not pieces[-1].endswith("\n"):
                pieces.pop()
                incomplete += 1
            lines.extend(pieces)
        result = summarize(lines)
        result["incomplete_final_lines_ignored"] = incomplete
    else:
        service = device_service(args.bundle_id, args.udid)
        try:
            result = collect(service, args.output_root) if args.command == "collect" else select_profile(service, args.name)
        finally:
            service.close()
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.command == "analyze" and args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
