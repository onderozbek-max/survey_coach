// Tool-denied Wibey streaming adapter. No shell, filesystem or browser tools exposed.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const [service, promptFile, mcpFile, model] = process.argv.slice(2);
const { executeHeadlessMode } = await import(pathToFileURL(service).href);
const code = await executeHeadlessMode({
  prompt: readFileSync(promptFile, 'utf8'), model, outputFormat: 'json-stream',
  disallowedTools: '*', maxTurns: 1, mcpConfigPath: mcpFile, cwd: process.cwd(),
});
process.exit(code);
