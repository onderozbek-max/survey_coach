"""Tool-denied planning adapter contract, no external model calls."""
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from surveycoach.llm.planner import WibeyPlanner
from surveycoach.llm.base import LlmError
from surveycoach.reader.strategies import Strategy


def test_planner_adapter_denies_tools_and_parses_stream(monkeypatch, tmp_path):
    import surveycoach.llm.planner as module
    binary = tmp_path / 'dist/app.js'
    binary.parent.mkdir()
    binary.touch()
    service = binary.parent / 'services/headlessModeService.js'
    service.parent.mkdir()
    service.write_text('disallowedTools: options.disallowedTools\n...disallowedToolsList\ndisallowedTools: [\noptions.mcpConfigPath')
    monkeypatch.setattr(module.shutil, 'which', lambda name: str(binary) if name == 'wibey' else '/bin/bun')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert json.loads(Path(command[4]).read_text()) == {'mcpServers': {}}
        content = '{"actions":[{"op":"wait"}]}'
        return SimpleNamespace(returncode=0, stdout=json.dumps({'type': 'content_delta', 'data': {'content': content}}))
    monkeypatch.setattr(module.subprocess, 'run', run)
    result = WibeyPlanner().complete_json('system', 'untrusted', Strategy)
    assert result.actions[0].op == 'wait'
    adapter = Path(calls[0][1]).read_text()
    assert "disallowedTools: '*'" in adapter
    assert 'maxTurns: 1' in adapter


def test_planner_rejects_local_image_transmission(monkeypatch):
    planner = object.__new__(WibeyPlanner)
    with pytest.raises(LlmError):
        planner.complete_json('system', 'data', Strategy, images=[Path('/tmp/private.png')])
