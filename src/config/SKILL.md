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