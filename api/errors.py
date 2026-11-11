"""Domain errors raised by services; handler.py turns them into HTTP responses.

Services stay free of FastAPI so the same code can be reused later (e.g. by AI assistant tools).
"""


class ApiError(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFound(ApiError):
    status_code = 404


class Forbidden(ApiError):
    status_code = 403


class Conflict(ApiError):
    status_code = 409
