class ApiError(Exception):
    def __init__(self, message, status_code=400, code="invalid_request"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class NotFoundError(ApiError):
    def __init__(self, message):
        super().__init__(message, status_code=404, code="not_found")


class ConflictError(ApiError):
    def __init__(self, message):
        super().__init__(message, status_code=409, code="conflict")


def validate_object(payload, allowed_fields, required_fields=()):
    if not isinstance(payload, dict):
        raise ApiError("A JSON object is required.")
    unknown = set(payload) - set(allowed_fields)
    if unknown:
        raise ApiError(f"Unknown field(s): {', '.join(sorted(unknown))}.")
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ApiError(f"Missing required field(s): {', '.join(missing)}.")
