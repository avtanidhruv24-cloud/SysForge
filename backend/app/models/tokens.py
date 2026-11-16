"""
SysForge — Token domain models.

These are the Pydantic contracts for lexical analysis output.  The Lexer
(Phase 3) must produce ``Token`` instances that satisfy these models.  The
frontend ``/lexical`` view will render these records in its data table.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.common.enums import TokenType


class SourceSpan(BaseModel):
    """
    Pinpoints a contiguous region of source text.

    Used by tokens, syntax nodes, and diagnostics so the frontend can
    highlight the relevant source span in the editor.
    """

    line: int = Field(ge=1, description="1-based line number.")
    column: int = Field(ge=1, description="1-based column number (start of span).")
    length: int = Field(ge=1, description="Number of characters in the span.")

    model_config = {
        "json_schema_extra": {
            "example": {"line": 2, "column": 1, "length": 5}
        }
    }


class Token(BaseModel):
    """
    A single lexical token produced by the SysForge lexer.

    Every non-whitespace, non-comment element of a source line becomes a
    token.  Comments are tokenised (type=COMMENT) but are not passed to the
    parser.

    Example JSON::

        {
            "type": "IMPERATIVE",
            "value": "MOVER",
            "line": 2,
            "column": 1,
            "span": {"line": 2, "column": 1, "length": 5}
        }
    """

    type: TokenType = Field(description="Lexical category of this token.")

    value: str = Field(
        min_length=1,
        description="Raw text of the token exactly as it appears in the source.",
    )

    line: int = Field(ge=1, description="1-based source line where this token starts.")

    column: int = Field(
        ge=1, description="1-based column where this token starts."
    )

    span: SourceSpan | None = Field(
        default=None,
        description="Precise source span.  Set when the lexer tracks character offsets.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "type": "IMPERATIVE",
                "value": "MOVER",
                "line": 2,
                "column": 1,
                "span": {"line": 2, "column": 1, "length": 5},
            }
        }
    }


class LexerResult(BaseModel):
    """
    Complete output of the lexical analysis stage.

    The ``tokens`` list contains every token in source order, including
    NEWLINE and EOF sentinels.  ``diagnostics`` carries any errors or
    warnings produced; a non-empty error list means ``success`` is
    ``False``.
    """

    tokens: list[Token] = Field(
        default_factory=list,
        description="All tokens produced from the source, in order.",
    )

    diagnostics: list[dict] = Field(
        default_factory=list,
        description=(
            "Diagnostic messages (errors / warnings) produced during lexing.  "
            "Each item mirrors ``EngineDiagnostic`` serialised to a dict."
        ),
    )

    success: bool = Field(
        default=True,
        description="``False`` if any fatal lexical errors were encountered.",
    )

    token_count: int = Field(
        default=0,
        ge=0,
        description="Total number of tokens (excluding EOF sentinel).",
    )
