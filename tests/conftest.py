import pytest

import config


@pytest.fixture(autouse=True)
def isolate_resources_dir(tmp_path, monkeypatch):
    """Point the resource library at a temp directory for every test.

    run_pipeline reads enabled sources, so without this a real library on the
    developer's machine would leak into pipeline and server tests and change
    what the agents receive — failures that would look mysterious.
    """
    monkeypatch.setattr(config, "RESOURCES_DIR", tmp_path / "resources_data")
