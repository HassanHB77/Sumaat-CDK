# Sumaat

Pickup-only food ordering POC for Al-Ahsa (AWS Builder Accelerator, Nov 2026).
Infrastructure is AWS CDK in Python, managed with [uv](https://docs.astral.sh/uv/).

## Layout

```
app.py            # CDK app: stacks in deploy order, cdk-nag, project=sumaat tag
infra/            # CDK stacks
functions/        # small Lambdas (e.g. Cognito triggers)
api/              # FastAPI + Mangum Lambda
tests/unit/       # pytest
```

## Setup

```
uv sync                 # installs Python 3.14 + all deps into .venv
uv run pytest -q        # unit tests
uv run cdk synth        # synth + cdk-nag checks
uv run cdk deploy <Stack> --outputs-file outputs.json
```

Region: `us-east-1`. Every resource is tagged `project=sumaat`.
