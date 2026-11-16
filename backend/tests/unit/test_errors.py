"""
Unit tests — Error models and exception hierarchy.

Verifies that the structured error system serialises correctly and that
each exception subclass carries the right defaults.
"""

from __future__ import annotations

import pytest

from app.core.errors import (
    AIServiceError,
    AssemblerError,
    EmptySourceError,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    ErrorSeverity,
    ExecutionError,
    InvalidRequestError,
    LexicalError,
    LinkerError,
    LoaderError,
    NotImplementedError_,
    SourceTooLargeError,
    SysForgeError,
    SyntaxError_,
)


class TestErrorDetail:
    def test_required_fields(self):
        detail = ErrorDetail(code=ErrorCode.LEXICAL_ERROR, message="bad token")
        assert detail.code == ErrorCode.LEXICAL_ERROR
        assert detail.message == "bad token"
        assert detail.severity == ErrorSeverity.ERROR

    def test_optional_fields_default_to_none(self):
        detail = ErrorDetail(code=ErrorCode.SYNTAX_ERROR, message="oops")
        assert detail.line is None
        assert detail.column is None
        assert detail.stage is None
        assert detail.details is None

    def test_serialises_to_dict(self):
        detail = ErrorDetail(
            code=ErrorCode.UNDEFINED_SYMBOL,
            message="LOOP not found",
            stage="pass-two",
            line=5,
        )
        d = detail.model_dump()
        assert d["code"] == "UNDEFINED_SYMBOL"
        assert d["stage"] == "pass-two"
        assert d["line"] == 5


class TestErrorResponse:
    def test_wraps_error_detail(self):
        detail = ErrorDetail(code=ErrorCode.INVALID_REQUEST, message="bad")
        response = ErrorResponse(error=detail)
        assert response.error.code == ErrorCode.INVALID_REQUEST

    def test_serialises_correctly(self):
        detail = ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message="boom")
        d = ErrorResponse(error=detail).model_dump()
        assert "error" in d
        assert d["error"]["code"] == "INTERNAL_ERROR"


class TestSysForgeError:
    def test_base_exception_fields(self):
        exc = SysForgeError(
            code=ErrorCode.LEXICAL_ERROR,
            message="bad char",
            http_status=422,
            stage="lexical",
            line=3,
            column=7,
        )
        assert exc.code == ErrorCode.LEXICAL_ERROR
        assert exc.http_status == 422
        assert exc.stage == "lexical"
        assert exc.line == 3
        assert exc.column == 7
        assert str(exc) == "bad char"

    def test_to_detail_conversion(self):
        exc = SysForgeError(
            code=ErrorCode.DUPLICATE_SYMBOL,
            message="LOOP defined twice",
            stage="pass-one",
            line=4,
        )
        detail = exc.to_detail()
        assert isinstance(detail, ErrorDetail)
        assert detail.code == ErrorCode.DUPLICATE_SYMBOL
        assert detail.line == 4

    def test_to_response_conversion(self):
        exc = SysForgeError(
            code=ErrorCode.MISSING_END,
            message="END not found",
        )
        response = exc.to_response()
        assert isinstance(response, ErrorResponse)
        assert response.error.code == ErrorCode.MISSING_END


class TestConcreteExceptions:
    def test_not_implemented_error(self):
        exc = NotImplementedError_("lexical")
        assert exc.code == ErrorCode.NOT_IMPLEMENTED
        assert exc.http_status == 501
        assert "lexical" in exc.message

    def test_empty_source_error(self):
        exc = EmptySourceError()
        assert exc.code == ErrorCode.EMPTY_SOURCE
        assert exc.http_status == 422

    def test_source_too_large_error(self):
        exc = SourceTooLargeError(max_chars=1000, actual_chars=5000)
        assert exc.code == ErrorCode.SOURCE_TOO_LARGE
        assert exc.http_status == 413
        assert exc.details is not None
        assert exc.details["max_chars"] == 1000

    def test_invalid_request_error(self):
        exc = InvalidRequestError("bad field")
        assert exc.code == ErrorCode.INVALID_REQUEST
        assert exc.http_status == 422

    def test_lexical_error_defaults(self):
        exc = LexicalError("unexpected @", line=2, column=5)
        assert exc.code == ErrorCode.LEXICAL_ERROR
        assert exc.stage == "lexical"
        assert exc.line == 2

    def test_assembler_error(self):
        exc = AssemblerError("duplicate LOOP", stage="pass-one", line=4)
        assert exc.stage == "pass-one"
        assert exc.line == 4

    def test_execution_error(self):
        exc = ExecutionError("division by zero")
        assert exc.stage == "execution"
        assert exc.http_status == 422

    def test_ai_service_error_is_503(self):
        exc = AIServiceError("OpenAI unavailable")
        assert exc.http_status == 503
