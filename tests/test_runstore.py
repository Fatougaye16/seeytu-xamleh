from datetime import datetime

import pytest

import config
import runstore


@pytest.fixture(autouse=True)
def isolated_output(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    yield


def _outputs():
    return {
        "research": "# Research\nbody",
        "learning": "# Learning\nbody",
        "project": "# Project\nbody",
        "linkedin": "post",
        "substack": "article",
        "notion": "reference",
        "combined": "raw writer response",
    }


def test_mint_run_id_is_slug_plus_timestamp():
    when = datetime(2026, 8, 9, 14, 5)
    assert runstore.mint_run_id("Vector databases for AI", when) == (
        "vector-databases-for-ai-20260809-1405"
    )


def test_mint_run_id_disambiguates_collisions():
    when = datetime(2026, 8, 9, 14, 5)
    first = runstore.mint_run_id("Same topic", when)
    runstore.write_run(first, "Same topic", _outputs(), {"model": "m"})
    second = runstore.mint_run_id("Same topic", when)
    assert second != first
    assert second.endswith("-2")


def test_write_run_creates_seven_files_and_metadata():
    written = runstore.write_run("demo-20260809-1405", "Demo", _outputs(), {"model": "m"})
    assert len(written) == 7
    directory = runstore.safe_run_dir("demo-20260809-1405")
    assert (directory / "01-research-brief.md").read_text(encoding="utf-8") == "# Research\nbody"
    assert (directory / "04-writer-combined.md").exists()
    assert (directory / "run.json").exists()


def test_write_run_survives_non_ascii_content():
    outputs = _outputs() | {"research": "em—dash, curly ’quote’, emoji 🚀"}
    runstore.write_run("uni-20260809-1405", "Unicode", outputs, {"model": "m"})
    body = (runstore.safe_run_dir("uni-20260809-1405") / "01-research-brief.md").read_text(
        encoding="utf-8"
    )
    assert "🚀" in body


def test_read_run_reports_topic_and_files():
    runstore.write_run("demo-20260809-1405", "Demo Topic", _outputs(), {"model": "m"})
    run = runstore.read_run("demo-20260809-1405")
    assert run["topic"] == "Demo Topic"
    assert run["model"] == "m"
    assert [entry["key"] for entry in run["files"]][0] == "research"
    assert run["files"][0]["word_count"] > 0


def test_list_runs_is_newest_first():
    for run_id in ("a-20260101-0900", "b-20260808-0900", "c-20260809-0900"):
        runstore.write_run(run_id, run_id, _outputs(), {"model": "m"})
    assert [run["run_id"] for run in runstore.list_runs()] == [
        "c-20260809-0900",
        "b-20260808-0900",
        "a-20260101-0900",
    ]


def test_delete_run_removes_the_folder():
    runstore.write_run("gone-20260809-1405", "Gone", _outputs(), {"model": "m"})
    runstore.delete_run("gone-20260809-1405")
    assert not runstore.safe_run_dir("gone-20260809-1405").exists()


@pytest.mark.parametrize(
    "run_id",
    ["../secrets", "..", "a/../../b", "C:/Windows", "sub/dir", "a\\b", ""],
)
def test_safe_run_dir_rejects_traversal(run_id):
    with pytest.raises(runstore.UnsafePath):
        runstore.safe_run_dir(run_id)


@pytest.mark.parametrize("filename", ["../../config.py", "..", "sub/file.md", "a\\b.md", ""])
def test_safe_run_file_rejects_traversal(filename):
    with pytest.raises(runstore.UnsafePath):
        runstore.safe_run_file("demo-20260809-1405", filename)


def test_safe_run_file_rejects_unknown_filenames():
    with pytest.raises(runstore.UnsafePath):
        runstore.safe_run_file("demo-20260809-1405", "arbitrary.md")


def test_delete_run_rejects_traversal():
    with pytest.raises(runstore.UnsafePath):
        runstore.delete_run("../..")
