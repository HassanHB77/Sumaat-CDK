# Reuse the API test fixtures (moto table + Cognito, Riyadh clock, a seeded shop) for the agent's tools.
from tests.unit.api.conftest import api_env, clock, ddb, make_client, shop  # noqa: F401
