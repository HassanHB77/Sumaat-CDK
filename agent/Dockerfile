# Sumaat AI agent container for Bedrock AgentCore Runtime (must be linux/arm64, listen on :8080).
# Build context = repo root (the agent reuses the api/ package for restaurants/menus).
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY agent/requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /app/agent/requirements.txt

COPY api /app/api
COPY agent /app/agent

# Don't run as root.
RUN useradd --create-home --uid 1000 agent
USER agent

EXPOSE 8080
CMD ["python", "-m", "agent.main"]
