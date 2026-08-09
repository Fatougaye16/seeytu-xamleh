import pytest

import prompts


def test_agents_are_in_pipeline_order():
    assert prompts.AGENTS == ["scout", "architect", "builder", "publisher"]


def test_agent_meta_is_complete():
    for agent in prompts.AGENTS:
        meta = prompts.AGENT_META[agent]
        assert meta["emoji"] and meta["name"] and meta["activity"]
    assert prompts.AGENT_META["scout"]["name"] == "The Scout"
    assert prompts.AGENT_META["publisher"]["name"] == "The Publisher"


def test_agent_aliases_cover_the_documented_cli_names():
    # The names the spec's CLI examples use, mapped to internal agent keys.
    assert prompts.AGENT_ALIASES["research"] == "scout"
    assert prompts.AGENT_ALIASES["curriculum"] == "architect"
    assert prompts.AGENT_ALIASES["project"] == "builder"
    assert prompts.AGENT_ALIASES["writer"] == "publisher"
    # Internal keys must also resolve to themselves.
    for agent in prompts.AGENTS:
        assert prompts.AGENT_ALIASES[agent] == agent


def test_every_system_prompt_injects_the_profile():
    marker = "How I learn"
    for agent in prompts.AGENTS:
        assert marker in prompts.system_prompt(agent)


def test_every_system_prompt_has_a_persona_and_bans_hedging():
    for agent in prompts.AGENTS:
        text = prompts.system_prompt(agent).lower()
        assert "you are" in text
        assert "do not" in text
        assert "verify before publishing" in text


def test_publisher_prompt_names_all_three_section_headers():
    text = prompts.system_prompt("publisher")
    assert "## LINKEDIN" in text
    assert "## SUBSTACK" in text
    assert "## NOTION" in text


def test_publisher_prompt_states_the_word_count_targets():
    text = prompts.system_prompt("publisher")
    assert "150" in text and "300" in text
    assert "800" in text and "1500" in text


def test_publisher_requires_a_verify_block_in_each_of_the_three_pieces():
    """One block at the end lands only in the NOTION section once split."""
    text = prompts.system_prompt("publisher")
    assert "each of the three" in text.lower()
    assert text.lower().count("verify before publishing") >= 2


def test_publisher_forbids_fabricated_first_person_experience():
    text = prompts.system_prompt("publisher").lower()
    assert "first-person" in text or "first person" in text
    assert "never invent" in text or "do not invent" in text


def test_publisher_demands_multiple_linkedin_paragraphs():
    text = prompts.system_prompt("publisher").lower()
    assert "blank line" in text
    assert "at least three paragraphs" in text


def test_architect_prompt_requires_a_connecting_the_dots_phase():
    assert "connecting the dots" in prompts.system_prompt("architect").lower()


def test_scout_user_prompt_contains_only_the_topic():
    text = prompts.user_prompt("scout", "vector databases", {})
    assert "vector databases" in text
    assert "RESEARCH BRIEF" not in text


def test_later_agents_receive_all_prior_outputs():
    prior = {"research": "R-CONTENT", "learning": "L-CONTENT", "project": "P-CONTENT"}
    architect = prompts.user_prompt("architect", "topic", prior)
    assert "R-CONTENT" in architect
    assert "L-CONTENT" not in architect  # the Architect has not seen the path yet

    builder = prompts.user_prompt("builder", "topic", prior)
    assert "R-CONTENT" in builder and "L-CONTENT" in builder
    assert "P-CONTENT" not in builder

    publisher = prompts.user_prompt("publisher", "topic", prior)
    assert all(
        marker in publisher for marker in ("R-CONTENT", "L-CONTENT", "P-CONTENT")
    )


def test_user_prompt_rejects_unknown_agent():
    with pytest.raises(KeyError):
        prompts.user_prompt("nobody", "topic", {})


def test_profile_round_trips(tmp_path, monkeypatch):
    path = tmp_path / "profile.md"
    monkeypatch.setattr(prompts, "PROFILE_PATH", path)
    prompts.save_profile("## Who I am\nem—dash and emoji 🚀\n")
    assert "🚀" in prompts.load_profile()


def test_load_profile_falls_back_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "PROFILE_PATH", tmp_path / "absent.md")
    assert prompts.load_profile().strip() != ""
