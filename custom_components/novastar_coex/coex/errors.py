"""Exception hierarchy for the COEX client."""

from __future__ import annotations

from .const import ERROR_CODES


class CoexError(Exception):
    """Base class for every error raised by this package."""


class CoexConnectionError(CoexError):
    """The controller could not be reached or did not answer with a valid envelope."""


class CoexApiError(CoexError):
    """The controller answered with an error ``code`` in the JSON envelope."""

    def __init__(self, code: int, message: str = "", path: str | None = None) -> None:
        self.code = code
        self.message = message
        self.path = path
        super().__init__(str(self))

    def __str__(self) -> str:
        name = ERROR_CODES.get(self.code, "Unknown")
        where = f" [{self.path}]" if self.path else ""
        return f"COEX error {self.code} ({name}): {self.message}{where}"


class CoexDeviceLocked(CoexApiError):
    """The controller is locked by VMP running on another machine.

    NovaStar's VMP desktop app takes an exclusive control session. While it is
    connected from a different host the HTTP API answers ``"device locked"``.
    Close VMP (or run it on the same host/IP as the API caller) to clear it.
    """
