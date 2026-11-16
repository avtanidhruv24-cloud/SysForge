"""
SysForge — Syntax analysis domain models.

The Parser (Phase 3) consumes the token stream from the Lexer and produces
``ParsedStatement`` records, one per non-empty source line.  These drive the
frontend ``/syntax`` view.

Statement structure in the SysForge educational language
---------------------------------------------------------
Each source line follows one of these patterns:

    [LABEL]  DIRECTIVE  [OPERAND]         START 100 / END / LTORG
    [LABEL]  MNEMONIC   REGISTER, OPERAND  MOVER AREG ='5'
    [LABEL]  MNEMONIC   REGISTER, OPERAND  ADD   BREG RESULT
    [LABEL]  BC         CONDITION, LABEL   BC    LT   LOOP
    [LABEL]  DC/DS      VALUE              RESULT DS 1

All fields except MNEMONIC are optional depending on the statement type.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.tokens import SourceSpan, Token
from engine.common.enums import (
    ConditionCode,
    DeclarativeMnemonic,
    Directive,
    ImperativeMnemonic,
    IntermediateClass,
    Register,
)


class SyntaxError_(BaseModel):
    """A single syntax error attached to a parsed statement."""

    message: str = Field(description="Human-readable description.")
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    token_value: str | None = Field(
        default=None, description="The token that triggered the error."
    )
    expected: str | None = Field(
        default=None,
        description="What the parser expected at this position.",
    )


class ParsedStatement(BaseModel):
    """
    A single parsed source statement.

    One ``ParsedStatement`` is produced per non-empty, non-comment line.
    The ``is_valid`` flag is ``False`` if the parser could not fully
    recognise the statement (syntax error).
    """

    line_number: int = Field(ge=1, description="1-based source line number.")

    label: str | None = Field(
        default=None,
        description="Label defined on this line, if present (without colon).",
    )

    # Exactly one of directive / imperative / declarative will be set
    directive: Directive | None = Field(
        default=None,
        description="Assembler directive (START, END, ORIGIN, EQU, LTORG).",
    )
    imperative: ImperativeMnemonic | None = Field(
        default=None,
        description="Executable mnemonic (ADD, MOVER, BC, …).",
    )
    declarative: DeclarativeMnemonic | None = Field(
        default=None,
        description="Data-definition mnemonic (DC, DS).",
    )

    register: Register | None = Field(
        default=None,
        description="First register operand, when present.",
    )

    condition_code: ConditionCode | None = Field(
        default=None,
        description="Condition code operand (used with BC).",
    )

    operand: str | None = Field(
        default=None,
        description=(
            "Second operand as a raw string: symbol name, literal (='n'), "
            "or integer constant."
        ),
    )

    # Classification used by Pass-I
    statement_class: IntermediateClass | None = Field(
        default=None,
        description="IS / DL / AD — classification for intermediate code.",
    )

    # Original tokens (useful for the frontend source-span highlighting)
    tokens: list[Token] = Field(
        default_factory=list,
        description="Tokens that make up this statement, in order.",
    )

    span: SourceSpan | None = Field(
        default=None,
        description="Source span covering the entire statement.",
    )

    is_valid: bool = Field(
        default=True,
        description="``False`` if the parser detected a syntax error on this line.",
    )

    errors: list[SyntaxError_] = Field(
        default_factory=list,
        description="Syntax errors found on this line.",
    )


class SyntaxResult(BaseModel):
    """
    Complete output of the syntax analysis stage.

    Contains one ``ParsedStatement`` per non-empty source line plus any
    global diagnostics that span multiple lines.
    """

    statements: list[ParsedStatement] = Field(
        default_factory=list,
        description="Parsed statements in source order.",
    )

    diagnostics: list[dict] = Field(
        default_factory=list,
        description="Global syntax diagnostics (errors / warnings).",
    )

    success: bool = Field(
        default=True,
        description="``False`` if any fatal syntax errors were encountered.",
    )

    statement_count: int = Field(
        default=0,
        ge=0,
        description="Total number of parsed statements.",
    )
