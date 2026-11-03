# Reader progression rules

| Rule | Match | Handler | Verification |
|---|---|---|---|
| native-answers | supported native or ARIA answer groups | answer_groups | answer state observed before forward action |
| staged-png | file input accepting PNG and optional Add Media control | answer_groups | media commit then verified next-page transition |
| validation-repair | field-local length errors or explicit selection counts | advance | verified next-page transition |

## Limits

- repair_attempts: 3
- model_calls: 2
- model_seconds: 45
- strategy_actions: 16

Learned strategies are provisional, local, origin/control-scoped and quarantined on first replay failure.
Strategies cannot execute code, read arbitrary files, bypass transport policy or establish full branch coverage.
