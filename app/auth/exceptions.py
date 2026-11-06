class AuthError(Exception):
    """Base class for authentication domain errors."""


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InactiveUser(AuthError):
    pass


class InvalidAccessToken(AuthError):
    pass


class InvalidRefreshToken(AuthError):
    pass


class RefreshTokenReuseDetected(AuthError):
    pass


class RegistrationDisabled(AuthError):
    pass
