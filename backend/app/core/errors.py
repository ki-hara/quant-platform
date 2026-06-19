class AppError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    pass


class ValidationAppError(AppError, ValueError):
    pass


class MarketDataError(AppError):
    pass
