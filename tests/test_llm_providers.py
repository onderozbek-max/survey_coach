"""The LLM provider layer. WibeyProvider is tested against a fake `wibey` script, so the subprocess
contract (prompt file in, JSON file out, stdout ignored, fixed model) is checked without the network."""
import os
import stat
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from surveycoach.llm import ASSESSMENT_MODEL, FakeProvider, LlmError, LlmUnavailable, WibeyProvider


class Probe(BaseModel):
    label: str
    score: int


GOOD = '{"label": "ok_value", "score": 3}'


def fake_wibey(tmp_path: Path, body: str) -> str:
    """A stand-in `wibey` executable. It sees `-f <prompt> -m <model>` and finds OUTPUT_FILE in the prompt."""
    script = tmp_path / "wibey"
    script.write_text("#!/bin/sh\n"
                      'prompt="$2"; model="$4"\n'
                      "out=$(grep '^OUTPUT_FILE: ' \"$prompt\" | head -1 | sed 's/^OUTPUT_FILE: //')\n"
                      f'echo "$model" > "{tmp_path}/model.txt"; pwd > "{tmp_path}/cwd.txt"; cp "$prompt" "{tmp_path}/last_prompt.txt"\n'
                      + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_it_reads_json_from_the_output_file_and_ignores_noisy_stdout(tmp_path):
    binary = fake_wibey(tmp_path, f'echo "**garbage** markdown that strips_underscores"\nprintf %s \'{GOOD}\' > "$out"\n')
    got = WibeyProvider(binary).complete_json("SYSTEM", "DATA", Probe)
    assert got == Probe(label="ok_value", score=3)           # underscores intact: stdout was never parsed


def test_it_always_uses_the_fixed_model_and_a_private_working_directory(tmp_path):
    binary = fake_wibey(tmp_path, f"printf %s '{GOOD}' > \"$out\"\n")
    WibeyProvider(binary).complete_json("SYSTEM", "DATA", Probe)
    assert (tmp_path / "model.txt").read_text().strip() == ASSESSMENT_MODEL == "gpt-6.1-sol"
    cwd = Path((tmp_path / "cwd.txt").read_text().strip()).resolve()
    assert cwd != Path.cwd().resolve() and not str(cwd).startswith(str(Path(__file__).parent.parent.resolve()))


def test_the_prompt_carries_the_system_text_the_schema_the_data_and_any_images(tmp_path):
    binary = fake_wibey(tmp_path, f"printf %s '{GOOD}' > \"$out\"\n")
    WibeyProvider(binary).complete_json("BE A JUDGE", "SURVEY TEXT HERE", Probe, images=[Path("/tmp/a.png")])
    prompt = (tmp_path / "last_prompt.txt").read_text()
    assert prompt.startswith("BE A JUDGE") and "SURVEY TEXT HERE" in prompt
    assert '"label"' in prompt and "OUTPUT_FILE: " in prompt and "IMAGE: /tmp/a.png" in prompt


def test_one_bad_answer_is_retried_once_with_the_error_and_then_accepted(tmp_path):
    counter = tmp_path / "count"
    binary = fake_wibey(tmp_path, f'n=$(cat "{counter}" 2>/dev/null || echo 0); echo $((n+1)) > "{counter}"\n'
                                  f'if [ "$n" = "0" ]; then printf %s "not json" > "$out"; else printf %s \'{GOOD}\' > "$out"; fi\n')
    assert WibeyProvider(binary).complete_json("S", "D", Probe).score == 3
    assert counter.read_text().strip() == "2"
    assert "invalid" in (tmp_path / "last_prompt.txt").read_text().lower()


def test_planning_provider_can_disable_output_retry(tmp_path):
    binary = fake_wibey(tmp_path, 'echo run >> "' + str(tmp_path / 'calls') + '"\nprintf %s invalid > "$out"\n')
    with pytest.raises(LlmError):
        WibeyProvider(binary, timeout=40, attempts=1).complete_json('S', 'D', Probe)
    assert (tmp_path / 'calls').read_text().splitlines() == ['run']


def test_two_bad_answers_raise_instead_of_guessing(tmp_path):
    binary = fake_wibey(tmp_path, 'printf %s \'{"label": 1}\' > "$out"\n')
    with pytest.raises(LlmError):
        WibeyProvider(binary).complete_json("S", "D", Probe)


def test_a_missing_binary_says_how_to_set_up_wibey(tmp_path):
    with pytest.raises(LlmUnavailable, match="wibey"):
        WibeyProvider(str(tmp_path / "no-such-wibey")).complete_json("S", "D", Probe)


def test_a_hung_call_times_out(tmp_path):
    binary = fake_wibey(tmp_path, "sleep 5\n")
    with pytest.raises(LlmError, match="timed out"):
        WibeyProvider(binary, timeout=1).complete_json("S", "D", Probe)


def test_the_binary_can_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SURVEYCOACH_WIBEY_BIN", fake_wibey(tmp_path, f"printf %s '{GOOD}' > \"$out\"\n"))
    assert WibeyProvider().complete_json("S", "D", Probe).label == "ok_value"


def test_the_fake_provider_returns_canned_answers_and_records_calls():
    fake = FakeProvider({"Probe": Probe(label="x", score=1)})
    assert fake.complete_json("sys", "data", Probe) == Probe(label="x", score=1)
    assert fake.calls == [("sys", "data", "Probe")]


def test_the_fake_provider_can_compute_its_answer_from_the_data():
    fake = FakeProvider({"Probe": lambda system, data: Probe(label=data.upper(), score=len(data))})
    assert fake.complete_json("s", "abc", Probe) == Probe(label="ABC", score=3)


def test_the_fake_provider_refuses_a_schema_it_has_no_answer_for():
    with pytest.raises(LlmError):
        FakeProvider({}).complete_json("s", "d", Probe)
