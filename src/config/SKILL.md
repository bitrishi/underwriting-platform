## Model Registry

Models are registered in `MODELS` dict in `bedrock.py`.
Tasks are mapped to models in `TASK_MODEL_MAP`.

To add a new model:
1. Add to `MODELS`: `"new_model": "vendor.model-id-v1:0"`
2. Map tasks: `"task_name": "new_model"` in `TASK_MODEL_MAP`
3. No code changes needed anywhere else

To swap a model for a task:
1. Change ONE line in `TASK_MODEL_MAP`
2. All code using `create_llm(task="task_name")` automatically uses the new model

## Guardrails (Week 5 Day 3)

`create_llm(...)` now supports Bedrock guardrails with per-role mapping.

Per-role mapping keys:
- `fetch_data` -> `fetch`
- `doc_review` -> `doc_review`
- `risk_scoring` -> `risk`
- `compliance` -> `compliance`

Configuration source:
- Global defaults from `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION`
- Optional role overrides via:
	- `BEDROCK_GUARDRAIL_ID_FETCH`, `BEDROCK_GUARDRAIL_VERSION_FETCH`
	- `BEDROCK_GUARDRAIL_ID_DOC_REVIEW`, `BEDROCK_GUARDRAIL_VERSION_DOC_REVIEW`
	- `BEDROCK_GUARDRAIL_ID_RISK`, `BEDROCK_GUARDRAIL_VERSION_RISK`
	- `BEDROCK_GUARDRAIL_ID_COMPLIANCE`, `BEDROCK_GUARDRAIL_VERSION_COMPLIANCE`

Operational rule:
- Always call `create_llm(task=...)` in agents so role guardrails are applied.
- Use explicit `guardrail_id` and `guardrail_version` only for controlled overrides.