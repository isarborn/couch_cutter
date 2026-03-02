"""
Tests for couch_cutter app.py
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Point MEDIA_ROOT at a temp directory before importing the app so that the
# module-level default doesn't matter.
import app as app_module


@pytest.fixture
def media_root(tmp_path):
    """A temporary directory that acts as the media root for each test."""
    app_module.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def client(media_root):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_video(directory: Path, name: str = "test.mp4") -> Path:
    """Create a tiny dummy video file."""
    p = directory / name
    p.write_bytes(b"\x00" * 64)
    return p


# ---------------------------------------------------------------------------
# _parse_time
# ---------------------------------------------------------------------------

class TestParseTime:
    def test_plain_seconds(self):
        assert app_module._parse_time("90") == 90.0

    def test_plain_float(self):
        assert app_module._parse_time("1.5") == 1.5

    def test_mm_ss(self):
        assert app_module._parse_time("1:30") == 90.0

    def test_hh_mm_ss(self):
        assert app_module._parse_time("1:02:03") == 3723.0

    def test_hh_mm_ss_frac(self):
        assert abs(app_module._parse_time("0:00:01.5") - 1.5) < 1e-9

    def test_invalid(self):
        with pytest.raises(ValueError):
            app_module._parse_time("not-a-time")


# ---------------------------------------------------------------------------
# _build_ffmpeg_cmd
# ---------------------------------------------------------------------------

class TestBuildFfmpegCmd:
    def test_single_segment(self, tmp_path):
        src = tmp_path / "in.mp4"
        dst = tmp_path / "out.mp4"
        segments = [{"start": 60.0, "end": 300.0}]
        cmd = app_module._build_ffmpeg_cmd(src, dst, segments)
        assert cmd[0] == "ffmpeg"
        assert str(src) in cmd
        assert str(dst) in cmd
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "trim=start=60.0:end=300.0" in fc
        assert "concat=n=1" in fc

    def test_two_segments(self, tmp_path):
        src = tmp_path / "in.mp4"
        dst = tmp_path / "out.mp4"
        segments = [{"start": 0.0, "end": 600.0}, {"start": 900.0, "end": 1800.0}]
        cmd = app_module._build_ffmpeg_cmd(src, dst, segments)
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "concat=n=2" in fc
        assert "v0" in fc
        assert "v1" in fc


# ---------------------------------------------------------------------------
# GET /api/files
# ---------------------------------------------------------------------------

class TestApiFiles:
    def test_root_listing(self, client, media_root):
        make_video(media_root, "movie.mp4")
        (media_root / "subdir").mkdir()
        res = client.get("/api/files")
        assert res.status_code == 200
        data = json.loads(res.data)
        names = [e["name"] for e in data["entries"]]
        assert "subdir" in names
        assert "movie.mp4" in names

    def test_video_type(self, client, media_root):
        make_video(media_root, "show.ts")
        res = client.get("/api/files")
        data = json.loads(res.data)
        entry = next(e for e in data["entries"] if e["name"] == "show.ts")
        assert entry["type"] == "video"

    def test_dir_type(self, client, media_root):
        (media_root / "series").mkdir()
        res = client.get("/api/files")
        data = json.loads(res.data)
        entry = next(e for e in data["entries"] if e["name"] == "series")
        assert entry["type"] == "dir"

    def test_subdir(self, client, media_root):
        sub = media_root / "sub"
        sub.mkdir()
        make_video(sub, "ep1.mp4")
        res = client.get("/api/files?path=sub")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert any(e["name"] == "ep1.mp4" for e in data["entries"])

    def test_path_traversal_rejected(self, client, media_root):
        res = client.get("/api/files?path=../../etc")
        assert res.status_code == 400

    def test_hidden_files_excluded(self, client, media_root):
        (media_root / ".hidden").write_bytes(b"x")
        res = client.get("/api/files")
        data = json.loads(res.data)
        assert not any(e["name"].startswith(".") for e in data["entries"])


# ---------------------------------------------------------------------------
# POST /api/cut
# ---------------------------------------------------------------------------

class TestApiCut:
    def test_missing_file_field(self, client, media_root):
        res = client.post("/api/cut", json={"segments": [{"start": "0", "end": "10"}]})
        assert res.status_code == 400

    def test_missing_segments(self, client, media_root):
        make_video(media_root, "v.mp4")
        res = client.post("/api/cut", json={"file": "v.mp4", "segments": []})
        assert res.status_code == 400

    def test_file_not_found(self, client, media_root):
        res = client.post("/api/cut", json={
            "file": "nonexistent.mp4",
            "segments": [{"start": "0", "end": "10"}],
        })
        assert res.status_code == 404

    def test_non_video_rejected(self, client, media_root):
        p = media_root / "notes.txt"
        p.write_bytes(b"hello")
        res = client.post("/api/cut", json={
            "file": "notes.txt",
            "segments": [{"start": "0", "end": "10"}],
        })
        assert res.status_code == 400

    def test_start_after_end_rejected(self, client, media_root):
        make_video(media_root, "v.mp4")
        res = client.post("/api/cut", json={
            "file": "v.mp4",
            "segments": [{"start": "30", "end": "10"}],
        })
        assert res.status_code == 400

    def test_overlapping_segments_rejected(self, client, media_root):
        make_video(media_root, "v.mp4")
        res = client.post("/api/cut", json={
            "file": "v.mp4",
            "segments": [
                {"start": "0", "end": "30"},
                {"start": "20", "end": "60"},
            ],
        })
        assert res.status_code == 400

    def test_path_traversal_in_cut_rejected(self, client, media_root):
        res = client.post("/api/cut", json={
            "file": "../../etc/passwd",
            "segments": [{"start": "0", "end": "10"}],
        })
        assert res.status_code in (400, 404)

    def test_successful_cut(self, client, media_root):
        """Mock subprocess.run to simulate a successful ffmpeg run."""
        src = make_video(media_root, "rec.mp4")
        original_content = src.read_bytes()

        def fake_run(cmd, **kwargs):
            # Simulate ffmpeg writing a result file (the .cutting.mp4 temp file)
            tmp_dst = next(Path(a) for a in cmd if ".cutting" in str(a))
            tmp_dst.write_bytes(b"\xFF" * 32)

            class FakeResult:
                returncode = 0
                stderr = ""
            return FakeResult()

        with patch("app.subprocess.run", side_effect=fake_run):
            res = client.post("/api/cut", json={
                "file": "rec.mp4",
                "segments": [{"start": "10", "end": "50"}],
            })

        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["status"] == "ok"

        # Backup must exist
        bak = media_root / "rec.mp4.bak"
        assert bak.exists()
        assert bak.read_bytes() == original_content

        # Output must have replaced the original
        assert src.exists()
        assert src.read_bytes() == b"\xFF" * 32

    def test_ffmpeg_failure_rolls_back(self, client, media_root):
        """When ffmpeg fails, the original must not be replaced."""
        src = make_video(media_root, "rec.mp4")
        original_content = src.read_bytes()

        def fake_run(cmd, **kwargs):
            class FakeResult:
                returncode = 1
                stderr = "ffmpeg error"
            return FakeResult()

        with patch("app.subprocess.run", side_effect=fake_run):
            res = client.post("/api/cut", json={
                "file": "rec.mp4",
                "segments": [{"start": "0", "end": "60"}],
            })

        assert res.status_code == 500
        # Original must be unchanged
        assert src.read_bytes() == original_content
        # Backup must be cleaned up on failure
        bak = media_root / "rec.mp4.bak"
        assert not bak.exists()

    def test_ffmpeg_not_installed(self, client, media_root):
        make_video(media_root, "rec.mp4")

        with patch("app.subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            res = client.post("/api/cut", json={
                "file": "rec.mp4",
                "segments": [{"start": "0", "end": "60"}],
            })

        assert res.status_code == 500


# ---------------------------------------------------------------------------
# Index route
# ---------------------------------------------------------------------------

class TestIndex:
    def test_index(self, client, media_root):
        res = client.get("/")
        assert res.status_code == 200
        assert b"couch_cutter" in res.data
