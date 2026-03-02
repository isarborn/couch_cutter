"""
couch_cutter – web server for cutting TV recordings via ffmpeg.

Usage:
    python app.py [--media-root /path/to/recordings] [--host 0.0.0.0] [--port 5000]

The server lists video files under `media_root`, lets the user mark
  • the start of the content (skip lead-in)
  • commercial-break intervals (start / end pairs)
  • the end of the content (skip lead-out)

FFmpeg is then used to concatenate the kept segments.
The original file is renamed to <filename>.bak and the cut result
is written to the original filename.
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".ts", ".m4v", ".mov", ".mpg", ".mpeg"}
DEFAULT_MEDIA_ROOT = os.path.expanduser("~/Videos")

app = Flask(__name__)
log = logging.getLogger(__name__)

# Resolved at startup (see __main__ block)
MEDIA_ROOT: Path = Path(DEFAULT_MEDIA_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_path(rel: str) -> Path:
    """Return an absolute path that is guaranteed to be inside MEDIA_ROOT."""
    # Normalise and strip leading slash so Path joining works correctly.
    clean = Path(rel.lstrip("/"))
    resolved = (MEDIA_ROOT / clean).resolve()
    if MEDIA_ROOT not in resolved.parents and resolved != MEDIA_ROOT:
        abort(400, "Path outside media root")
    return resolved


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _parse_time(value: str) -> float:
    """Convert HH:MM:SS[.mmm] or a plain float (seconds) to float seconds."""
    value = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    raise ValueError(f"Cannot parse time value: {value!r}")


def _build_ffmpeg_cmd(src: Path, dst: Path, segments: list[dict]) -> list[str]:
    """
    Build an ffmpeg command that concatenates the given time *segments*.

    Each element of *segments* is a dict with keys "start" and "end"
    (both as float seconds).

    Returns the argument list for subprocess (without shell=True).
    """
    n = len(segments)
    filter_parts: list[str] = []
    for i, seg in enumerate(segments):
        s = seg["start"]
        e = seg["end"]
        filter_parts.append(
            f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]"
        )

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vout][aout]")

    filter_complex = ";".join(filter_parts)

    return [
        "ffmpeg",
        "-y",                   # overwrite output
        "-i", str(src),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        str(dst),
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/files")
def api_files():
    """
    List the contents of a directory relative to MEDIA_ROOT.

    Query param:
        path  – relative path (defaults to root)

    Returns JSON:
        {
          "path": "<relative path>",
          "entries": [
            {"name": "...", "type": "dir"|"video"|"file", "path": "..."},
            ...
          ]
        }
    """
    rel = request.args.get("path", "")
    directory = _safe_path(rel)

    if not directory.exists():
        abort(404, "Directory not found")
    if not directory.is_dir():
        abort(400, "Not a directory")

    entries = []
    try:
        items = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        abort(403, "Permission denied")

    for item in items:
        if item.name.startswith("."):
            continue
        rel_item = item.relative_to(MEDIA_ROOT)
        entry_type = "dir" if item.is_dir() else ("video" if _is_video(item) else "file")
        entries.append({"name": item.name, "type": entry_type, "path": str(rel_item)})

    # Build breadcrumb path segments
    parts = []
    current = Path(rel) if rel else Path(".")
    accumulated = Path(".")
    for part in Path(rel).parts if rel else []:
        accumulated = accumulated / part
        parts.append({"name": part, "path": str(accumulated)})

    return jsonify({"path": rel, "breadcrumbs": parts, "entries": entries})


@app.route("/api/cut", methods=["POST"])
def api_cut():
    """
    Cut a video file using ffmpeg.

    Request JSON:
        {
          "file": "<relative path to video>",
          "segments": [
            {"start": "HH:MM:SS", "end": "HH:MM:SS"},
            ...
          ]
        }

    The original file is renamed to <file>.bak.
    The cut result is written to the original filename.

    Returns JSON:
        {"status": "ok", "output": "<ffmpeg stderr>"}
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        abort(400, "Invalid JSON body")

    rel_file = data.get("file", "")
    if not rel_file:
        abort(400, "Missing 'file' field")

    raw_segments = data.get("segments")
    if not raw_segments or not isinstance(raw_segments, list):
        abort(400, "Missing or empty 'segments' list")

    src = _safe_path(rel_file)
    if not src.exists() or not src.is_file():
        abort(404, "Video file not found")
    if not _is_video(src):
        abort(400, "Not a supported video file")

    # Parse and validate segments
    segments: list[dict] = []
    for idx, seg in enumerate(raw_segments):
        try:
            start = _parse_time(str(seg["start"]))
            end = _parse_time(str(seg["end"]))
        except (KeyError, ValueError) as exc:
            abort(400, f"Invalid segment {idx}: {exc}")
        if start >= end:
            abort(400, f"Segment {idx}: start must be before end")
        segments.append({"start": start, "end": end})

    # Validate segments are ordered and non-overlapping
    for i in range(1, len(segments)):
        if segments[i]["start"] < segments[i - 1]["end"]:
            abort(400, f"Segments {i - 1} and {i} overlap")

    # Backup original
    backup = src.with_suffix(src.suffix + ".bak")
    try:
        shutil.copy2(src, backup)
    except OSError as exc:
        abort(500, f"Could not create backup: {exc}")

    # Build temporary output path to avoid overwriting src while ffmpeg reads it
    tmp_dst = src.with_suffix(".cutting" + src.suffix)
    cmd = _build_ffmpeg_cmd(src, tmp_dst, segments)
    log.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # ffmpeg not installed – clean up and report
        backup.unlink(missing_ok=True)
        abort(500, "ffmpeg is not installed or not on PATH")

    if result.returncode != 0:
        # Roll back: remove partial output, keep original untouched
        tmp_dst.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)
        return jsonify({
            "status": "error",
            "output": result.stderr,
        }), 500

    # Replace original with cut result
    try:
        tmp_dst.replace(src)
    except OSError as exc:
        tmp_dst.unlink(missing_ok=True)
        abort(500, f"Could not replace original file: {exc}")

    return jsonify({"status": "ok", "output": result.stderr})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(description="couch_cutter web server")
    parser.add_argument(
        "--media-root",
        default=DEFAULT_MEDIA_ROOT,
        help="Root directory for video files (default: ~/Videos)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = _parse_args()
    MEDIA_ROOT = Path(args.media_root).resolve()
    log.info("Media root: %s", MEDIA_ROOT)
    app.run(host=args.host, port=args.port, debug=args.debug)
