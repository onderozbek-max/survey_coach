"""Tool-denied Wibey inference via its streaming service; fail closed on incompatibility."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import ASSESSMENT_MODEL, LlmError, LlmUnavailable


class WibeyPlanner:
    """No model tools; output is parsed JSON, never a model-written file."""
    def __init__(self, binary: str | None = None, timeout: int = 40):
        executable = shutil.which(binary or 'wibey')
        if not executable:
            raise LlmUnavailable('Wibey is unavailable for strategy planning.')
        self.service = Path(executable).resolve().parent / 'services/headlessModeService.js'
        self.runtime = shutil.which('bun')
        self.timeout = timeout
        if not self.service.is_file() or not self.runtime:
            raise LlmUnavailable('Installed Wibey does not support the tool-denied planning adapter.')
        source = self.service.read_text()
        # Refuse versions where these streaming restrictions were not wired through.
        if not all(token in source for token in ('disallowedTools: options.disallowedTools', '...disallowedToolsList', 'disallowedTools: [', 'options.mcpConfigPath')):
            raise LlmUnavailable('Wibey tool-denial support could not be verified.')

    def complete_json(self, system, data, schema, images=()):
        if images:
            raise LlmError('Strategy planning does not transmit local images.')
        with tempfile.TemporaryDirectory(prefix='surveycoach-planner-') as folder:
            work = Path(folder)
            prompt = work / 'prompt.txt'
            prompt.write_text(system + '\nReturn only JSON, no tools or Markdown.\nSCHEMA: ' +
                              json.dumps(schema.model_json_schema()) + '\nUNTRUSTED PAGE DATA:\n' + data)
            prompt.chmod(0o600)
            mcp = work / 'mcp.json'
            mcp.write_text('{"mcpServers":{}}')
            try:
                result = subprocess.run([self.runtime, str(Path(__file__).with_name('planner.mjs')),
                    str(self.service), str(prompt), str(mcp), ASSESSMENT_MODEL], cwd=work,
                    capture_output=True, text=True, timeout=self.timeout, check=False)
            except subprocess.TimeoutExpired as error:
                raise LlmError('Tool-denied strategy planning timed out.') from error
            if result.returncode:
                raise LlmError('Tool-denied strategy planning failed.')
            content = ''
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if 'tool' in event.get('type', ''):
                    raise LlmError('Planner emitted an unexpected tool event.')
                if event.get('type') == 'content_delta':
                    content += event.get('data', {}).get('content', '')
            try:
                return schema.model_validate_json(content)
            except ValueError as error:
                raise LlmError('Planner did not return a valid strategy.') from error
