"""Single reference for built-in handler rules and adaptive execution budgets."""
import json
from pathlib import Path

RULESET = json.loads(Path(__file__).with_name('rules.json').read_text())
LIMITS = RULESET['limits']


def reference_markdown() -> str:
    rows = ['# Reader progression rules', '', '| Rule | Match | Handler | Verification |',
            '|---|---|---|---|']
    rows.extend('| ' + ' | '.join(rule[key] for key in ('id', 'match', 'handler', 'verify')) + ' |'
                for rule in RULESET['rules'])
    rows += ['', '## Limits', '']
    rows.extend(f'- {key}: {value}' for key, value in LIMITS.items())
    rows += ['', 'Learned strategies are provisional, local, origin/control-scoped and quarantined on first replay failure.',
             'Strategies cannot execute code, read arbitrary files, bypass transport policy or establish full branch coverage.', '']
    return '\n'.join(rows)
