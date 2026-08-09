import socket

import config


def test_defaults_are_sane():
    assert config.APP_NAME == "Seeytu-Xamleh"
    assert config.APP_SHORT_NAME == "Seeytu"
    assert config.NUM_CTX >= 16384, "num_ctx must be large enough for the Publisher's input"
    assert config.MAX_TOKENS == 4096
    assert config.OLLAMA_URL == "http://localhost:11434"
    assert config.MAX_CONCURRENT_RUNS >= 1


def test_find_free_port_skips_occupied_port():
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        occupied = taken.getsockname()[1]
        found = config.find_free_port(occupied)
        assert found != occupied
        assert found > occupied


def test_update_clamps_temperature():
    original_model, original_temperature = config.MODEL_NAME, config.TEMPERATURE
    try:
        assert config.update(None, 5.0)["temperature"] == 1.0
        assert config.update(None, -3.0)["temperature"] == 0.0
        assert config.update("some-model", 0.4) == {
            "model": "some-model",
            "temperature": 0.4,
        }
    finally:
        # Restore both: config holds module-level state shared by the whole suite.
        config.update(original_model, original_temperature)


def test_as_dict_reports_current_values():
    snapshot = config.as_dict()
    assert set(snapshot) >= {"model", "temperature", "num_ctx", "max_tokens", "output_dir"}
