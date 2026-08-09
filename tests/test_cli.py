import config
import run as entry


def test_banner_shows_both_names_and_the_model():
    text = entry.banner("gpt-oss:120b-cloud", "cloud")
    assert config.APP_NAME in text
    assert config.TAGLINE in text
    assert "gpt-oss:120b-cloud" in text
    assert "cloud" in text


def test_event_printer_reports_each_agent(capsys):
    printer = entry.cli_event_printer()
    printer({"type": "agent_start", "agent": "scout", "step": 1, "total": 4})
    printer({"type": "agent_complete", "agent": "scout", "step": 1, "output": "x" * 40})
    output = capsys.readouterr().out
    assert "The Scout" in output
    assert "1/4" in output


def test_event_printer_shows_the_hint_on_error(capsys):
    printer = entry.cli_event_printer()
    printer({
        "type": "error", "message": "Cannot reach Ollama.",
        "hint": "Start it with: ollama serve", "agent": "scout", "step": 1, "completed": [],
    })
    output = capsys.readouterr().out
    assert "ollama serve" in output


def test_argument_parsing_accepts_the_documented_flags():
    parsed = entry.parse_args(["--cli", "--agent", "research", "--topic", "vector databases"])
    assert parsed.cli is True
    assert parsed.agent == "research"
    assert parsed.topic == "vector databases"
