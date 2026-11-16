"""
SysForge — structured error model.

All errors surfaced by the API are instances of ``SysForgeError`` or one of
its subclasses.  FastAPI exception handlers in ``main.py`` convert these into
consistent JSON responses so the frontend always receives the same error
envelope regardless of which engine stage produced the failure.

Error code vocabulary
---------------------
Error codes are string constants (not integers) so they are self-documenting
in API responses and logs.  New codes should be added here — never scattered
across feature modules.

HTTP mapping
------------
Each ``SysForgeError`` subclass declares a default HTTP status code.
The exception handler in ``main.py`` reads ``exc.http_status``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Error code registry
# ---------------------------------------------------------------------------


class ErrorCode(StrEnum):
    """
    Canonical error codes for the SysForge toolchain.

    Codes are grouped by concern.  The prefix identifies the originating
    stage so the frontend can route the error to the correct view.
    """

    # --- General / API --------------------------------------------------
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INVALID_REQUEST = "INVALID_REQUEST"

    # --- Source ---------------------------------------------------------
    EMPTY_SOURCE = "EMPTY_SOURCE"
    SOURCE_TOO_LARGE = "SOURCE_TOO_LARGE"

    # --- Lexical analysis -----------------------------------------------
    LEXICAL_ERROR = "LEXICAL_ERROR"
    INVALID_CHARACTER = "INVALID_CHARACTER"
    UNTERMINATED_LITERAL = "UNTERMINATED_LITERAL"
    INVALID_LITERAL_FORMAT = "INVALID_LITERAL_FORMAT"

    # --- Syntax analysis ------------------------------------------------
    SYNTAX_ERROR = "SYNTAX_ERROR"
    UNEXPECTED_TOKEN = "UNEXPECTED_TOKEN"
    MISSING_OPERAND = "MISSING_OPERAND"
    EXTRA_OPERAND = "EXTRA_OPERAND"

    # --- Macro processor ------------------------------------------------
    MACRO_ERROR = "MACRO_ERROR"
    DUPLICATE_MACRO = "DUPLICATE_MACRO"
    UNDEFINED_MACRO = "UNDEFINED_MACRO"
    MACRO_ARGUMENT_MISMATCH = "MACRO_ARGUMENT_MISMATCH"

    # --- Assembler Pass-I -----------------------------------------------
    PASS1_ERROR = "PASS1_ERROR"
    DUPLICATE_SYMBOL = "DUPLICATE_SYMBOL"
    INVALID_START = "INVALID_START"
    MISSING_END = "MISSING_END"
    INVALID_MNEMONIC = "INVALID_MNEMONIC"
    INVALID_REGISTER = "INVALID_REGISTER"
    INVALID_OPERAND = "INVALID_OPERAND"

    # --- Assembler Pass-II ----------------------------------------------
    PASS2_ERROR = "PASS2_ERROR"
    UNDEFINED_SYMBOL = "UNDEFINED_SYMBOL"
    UNDEFINED_LITERAL = "UNDEFINED_LITERAL"

    # --- Linker ---------------------------------------------------------
    LINK_ERROR = "LINK_ERROR"
    UNRESOLVED_EXTERNAL = "UNRESOLVED_EXTERNAL"
    DUPLICATE_GLOBAL = "DUPLICATE_GLOBAL"

    # --- Loader ---------------------------------------------------------
    LOAD_ERROR = "LOAD_ERROR"
    ADDRESS_CONFLICT = "ADDRESS_CONFLICT"
    LOAD_ADDRESS_OUT_OF_RANGE = "LOAD_ADDRESS_OUT_OF_RANGE"

    # --- VM / Execution -------------------------------------------------
    EXECUTION_ERROR = "EXECUTION_ERROR"
    ILLEGAL_INSTRUCTION = "ILLEGAL_INSTRUCTION"
    MEMORY_ACCESS_VIOLATION = "MEMORY_ACCESS_VIOLATION"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    MAX_INSTRUCTIONS_EXCEEDED = "MAX_INSTRUCTIONS_EXCEEDED"

    # --- AI service -----------------------------------------------------
    AI_ERROR = "AI_ERROR"
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    AI_CONTEXT_MISSING = "AI_CONTEXT_MISSING"


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------


class ErrorSeverity(StrEnum):
    """Severity of a diagnostic message or exception."""

    ERROR = "ERROR"       # Fatal — processing cannot continue
    WARNING = "WARNING"   # Non-fatal — processing continues with caveats
    INFO = "INFO"         # Informational diagnostic


# ---------------------------------------------------------------------------
# Structured error detail (used both in API responses and exceptions)
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """
    A single structured diagnostic produced by the engine or API layer.

    Instances are embedded inside API error responses and also carried as
    ``details`` on ``SysForgeError`` exceptions.
    """

    code: ErrorCode = Field(description="Machine-readable error code.")

    message: str = Field(description="Human-readable description of the error.")

    severity: ErrorSeverity = Field(
        default=ErrorSeverity.ERROR,
        description="Severity level of this diagnostic.",
    )

    stage: str | None = Field(
        default=None,
        description=(
            "Pipeline stage that produced the error "
            "(e.g. 'lexical', 'syntax', 'pass-one')."
        ),
    )

    line: int | None = Field(
        default=None,
        ge=1,
        description="1-based source line number where the error occurred.",
    )

    column: int | None = Field(
        default=None,
        ge=1,
        description="1-based column number where the error occurred.",
    )

    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional additional context (token value, symbol name, etc.).",
    )


# ---------------------------------------------------------------------------
# API error response envelope
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """
    JSON envelope returned by the API for all 4xx / 5xx responses.

    The frontend reads ``error.code`` to decide which error surface to show.
    """

    error: ErrorDetail

    model_config = {"json_schema_extra": {
        "example": {
            "error": {
                "code": "LEXICAL_ERROR",
                "message": "Unexpected character '@' at line 3, column 5.",
                "severity": "ERROR",
                "stage": "lexical",
                "line": 3,
                "column": 5,
            }
        }
    }}


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class SysForgeError(Exception):
    """
    Base exception for all SysForge domain errors.

    Raised by the engine and service layers; caught by the FastAPI exception
    handler in ``main.py``, which converts it to an ``ErrorResponse``.

    Args:
        code:       ``ErrorCode`` identifying the problem.
        message:    Human-readable description.
        http_status: HTTP status code for the API response (default 400).
        stage:      Pipeline stage name (e.g. ``"lexical"``).
        line:       1-based source line.
        column:     1-based column.
        details:    Extra context dict.
        severity:   ``ErrorSeverity`` (defaults to ERROR).
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        http_status: int = 400,
        stage: str | None = None,
        line: int | None = None,
        column: int | None = None,
        details: dict[str, Any] | None = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.stage = stage
        self.line = line
        self.column = column
        self.details = details
        self.severity = severity

    def to_detail(self) -> ErrorDetail:
        """Convert this exception into a serialisable ``ErrorDetail``."""
        return ErrorDetail(
            code=self.code,
            message=self.message,
            severity=self.severity,
            stage=self.stage,
            line=self.line,
            column=self.column,
            details=self.details,
        )

    def to_response(self) -> ErrorResponse:
        """Wrap this exception as an ``ErrorResponse`` (for direct JSON return)."""
        return ErrorResponse(error=self.to_detail())


# ---------------------------------------------------------------------------
# Concrete exception subclasses
# ---------------------------------------------------------------------------


class NotImplementedError_(SysForgeError):
    """Raised when a pipeline stage exists in the API but is not yet built."""

    def __init__(self, stage: str) -> None:
        super().__init__(
            code=ErrorCode.NOT_IMPLEMENTED,
            message=f"Stage '{stage}' is not yet implemented.",
            http_status=501,
            stage=stage,
        )


class InvalidRequestError(SysForgeError):
    """Raised when the incoming request fails domain-level validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_REQUEST,
            message=message,
            http_status=422,
            details=details,
        )


class EmptySourceError(SysForgeError):
    """Raised when the submitted source code is empty or whitespace-only."""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.EMPTY_SOURCE,
            message="Source code must not be empty.",
            http_status=422,
            stage="lexical",
        )


class SourceTooLargeError(SysForgeError):
    """Raised when the submitted source exceeds the maximum allowed size."""

    def __init__(self, max_chars: int, actual_chars: int) -> None:
        super().__init__(
            code=ErrorCode.SOURCE_TOO_LARGE,
            message=(
                f"Source code is too large ({actual_chars} characters). "
                f"Maximum allowed: {max_chars}."
            ),
            http_status=413,
            details={"max_chars": max_chars, "actual_chars": actual_chars},
        )


class LexicalError(SysForgeError):
    """Raised by the Lexer for unrecognised or malformed input."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        code: ErrorCode = ErrorCode.LEXICAL_ERROR,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            http_status=422,
            stage="lexical",
            line=line,
            column=column,
        )


class SyntaxError_(SysForgeError):
    """Raised by the Parser for grammatically invalid statements."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        code: ErrorCode = ErrorCode.SYNTAX_ERROR,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            http_status=422,
            stage="syntax",
            line=line,
            column=column,
        )


class AssemblerError(SysForgeError):
    """Raised by Pass-I or Pass-II for assembler-level problems."""

    def __init__(
        self,
        message: str,
        stage: str = "pass-one",
        line: int | None = None,
        code: ErrorCode = ErrorCode.PASS1_ERROR,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            http_status=422,
            stage=stage,
            line=line,
        )


class LinkerError(SysForgeError):
    """Raised by the Linker."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.LINK_ERROR) -> None:
        super().__init__(
            code=code, message=message, http_status=422, stage="linker"
        )


class LoaderError(SysForgeError):
    """Raised by the Loader."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.LOAD_ERROR) -> None:
        super().__init__(
            code=code, message=message, http_status=422, stage="loader"
        )


class ExecutionError(SysForgeError):
    """Raised by the Virtual Machine during program execution."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.EXECUTION_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            http_status=422,
            stage="execution",
            details=details,
        )


class AIServiceError(SysForgeError):
    """Raised when the AI explanation/optimisation service is unavailable."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.AI_ERROR) -> None:
        super().__init__(
            code=code, message=message, http_status=503, stage="ai"
        )
