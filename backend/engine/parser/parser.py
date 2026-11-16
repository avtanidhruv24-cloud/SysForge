"""
SysForge — Deterministic Syntax Analyzer (Parser).

Consumes the ``LexerResult`` token stream produced by the Lexer and turns
it into a list of structured ``ParsedStatement`` records, one per
non-empty source line.

===========================================================================
Grammar table
===========================================================================

Every supported statement follows one of these patterns.  Token types are
written in UPPERCASE; optional elements are enclosed in [square brackets];
alternatives are separated by |.

  --- Assembler Directives (IntermediateClass = AD) ---

  [SYMBOL]  START   NUMBER
  [SYMBOL]  END
  [SYMBOL]  ORIGIN  NUMBER | SYMBOL
  [SYMBOL]  EQU     NUMBER | SYMBOL
  [SYMBOL]  LTORG

  --- Imperative Instructions (IntermediateClass = IS) ---

  [SYMBOL]  ADD    REGISTER  REGISTER | LITERAL | SYMBOL | NUMBER
  [SYMBOL]  SUB    REGISTER  REGISTER | LITERAL | SYMBOL | NUMBER
  [SYMBOL]  MULT   REGISTER  REGISTER | LITERAL | SYMBOL | NUMBER
  [SYMBOL]  MOVER  REGISTER  LITERAL  | SYMBOL  | NUMBER
  [SYMBOL]  MOVEM  REGISTER  SYMBOL
  [SYMBOL]  COMP   REGISTER  REGISTER | LITERAL | SYMBOL | NUMBER
  [SYMBOL]  BC     CONDITION_CODE  SYMBOL
  [SYMBOL]  DIV    REGISTER  REGISTER | LITERAL | SYMBOL | NUMBER
  [SYMBOL]  READ   SYMBOL
  [SYMBOL]  PRINT  SYMBOL
  [SYMBOL]  STOP

  --- Declarative Instructions (IntermediateClass = DL) ---

  [SYMBOL]  DC  NUMBER
  [SYMBOL]  DS  NUMBER

===========================================================================
Label handling
===========================================================================

The first token on a line determines whether a label is present:

  SYMBOL → tentative label, look ahead for the mnemonic in position 2
  Non-SYMBOL (DIRECTIVE | IMPERATIVE | DECLARATIVE) → no label, mnemonic is
  token 0.

Because the Lexer classifies all identifiers it cannot map to a keyword as
SYMBOL, a symbol appearing before a mnemonic is always a label.  A symbol
appearing AFTER a mnemonic is always an operand.

  LOOP  SUB  AREG  ='2'        →  label=LOOP,  mnemonic=SUB
  MOVER LOOP ='5'              →  label=None,  mnemonic=MOVER,  operand=LOOP

===========================================================================
Error recovery
===========================================================================

The parser processes one statement at a time.  If a statement is invalid,
an error is recorded in that statement's ``errors`` list and parsing
continues at the next statement.  A single bad line never aborts the entire
result.

===========================================================================
Responsibilities the parser does NOT have
===========================================================================

• Address assignment           → Assembler Pass-I
• Symbol table construction    → Assembler Pass-I
• Literal table construction   → Assembler Pass-I
• Undefined-symbol detection   → Assembler Pass-I / Pass-II
• Duplicate-symbol detection   → Assembler Pass-I
• Expression evaluation        → Assembler Pass-I
• Program-level flow rules
  (e.g. START must be first)   → Assembler Pass-I / semantic validation
"""

from __future__ import annotations

import dataclasses
from typing import Sequence

from app.models.syntax import ParsedStatement, SyntaxError_, SyntaxResult
from app.models.tokens import LexerResult, SourceSpan, Token
from engine.common.enums import (
    AnalysisStage,
    ConditionCode,
    DeclarativeMnemonic,
    Directive,
    ImperativeMnemonic,
    IntermediateClass,
    Register,
    TokenType,
)

# ---------------------------------------------------------------------------
# Operand-set constants for each mnemonic
# ---------------------------------------------------------------------------

# Token types that are valid as the *second* operand for arithmetic instructions
_ARITH_OP2 = frozenset({
    TokenType.REGISTER,
    TokenType.LITERAL,
    TokenType.SYMBOL,
    TokenType.NUMBER,
})

# MOVER second operand cannot be a bare register (it loads a value *into* one)
_MOVER_OP2 = frozenset({
    TokenType.LITERAL,
    TokenType.SYMBOL,
    TokenType.NUMBER,
})

# MOVEM second operand must be a symbol (memory address)
_MOVEM_OP2 = frozenset({TokenType.SYMBOL})

# Branch target must be a symbol
_BC_OP2 = frozenset({TokenType.SYMBOL})

# READ/PRINT work on a single memory symbol
_IO_OP1 = frozenset({TokenType.SYMBOL})

# ORIGIN / EQU accept a numeric constant or a symbol expression
_ORIGIN_EQU_OP = frozenset({TokenType.NUMBER, TokenType.SYMBOL})

# DC / DS accept only a numeric constant
_DC_DS_OP = frozenset({TokenType.NUMBER})

# START accepts only a numeric constant
_START_OP = frozenset({TokenType.NUMBER})


# ---------------------------------------------------------------------------
# Internal per-line token cursor
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _LineCursor:
    """
    A thin cursor over the non-comment, non-EOF tokens of one source line.

    All positions are expressed in terms of the index into ``tokens``.
    """

    tokens: list[Token]
    pos: int = 0

    @property
    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    @property
    def current(self) -> Token | None:
        return self.tokens[self.pos] if not self.at_end else None

    def peek(self, offset: int = 1) -> Token | None:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def advance(self) -> Token | None:
        tok = self.current
        if not self.at_end:
            self.pos += 1
        return tok

    def remaining(self) -> list[Token]:
        return self.tokens[self.pos:]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class Parser:
    """
    SysForge deterministic syntax analyzer.

    Usage::

        from engine.parser import Parser

        parser = Parser()
        syntax_result = parser.parse(lexer_result)

    The ``Parser`` instance is stateless between calls.
    """

    def parse(self, lexer_result: LexerResult) -> SyntaxResult:
        """
        Parse the token stream in *lexer_result* into structured statements.

        Args:
            lexer_result: Output of the Lexer stage.

        Returns:
            ``SyntaxResult`` with ``statements``, ``diagnostics``,
            ``success``, and ``statement_count`` populated.
        """
        if not lexer_result.tokens:
            return SyntaxResult(
                statements=[],
                diagnostics=[],
                success=True,
                statement_count=0,
            )

        # ----------------------------------------------------------------
        # Group tokens by line, dropping comments
        # ----------------------------------------------------------------
        line_map: dict[int, list[Token]] = {}
        for tok in lexer_result.tokens:
            if tok.type == TokenType.COMMENT:
                continue
            line_map.setdefault(tok.line, []).append(tok)

        # ----------------------------------------------------------------
        # Parse each non-empty line independently
        # ----------------------------------------------------------------
        statements: list[ParsedStatement] = []
        global_diagnostics: list[dict] = []
        has_errors = False

        for line_num in sorted(line_map.keys()):
            line_tokens = line_map[line_num]
            if not line_tokens:
                continue

            cursor = _LineCursor(tokens=line_tokens)
            stmt = self._parse_statement(cursor, line_num)
            statements.append(stmt)

            if not stmt.is_valid:
                has_errors = True
                # Promote per-statement errors to global diagnostics too
                for err in stmt.errors:
                    global_diagnostics.append({
                        "stage": AnalysisStage.SYNTAX,
                        "severity": "ERROR",
                        "code": "SYNTAX_ERROR",
                        "message": err.message,
                        "line": err.line,
                        "column": err.column,
                        "token_value": err.token_value,
                    })

        return SyntaxResult(
            statements=statements,
            diagnostics=global_diagnostics,
            success=not has_errors,
            statement_count=len(statements),
        )

    # ------------------------------------------------------------------
    # Statement dispatcher
    # ------------------------------------------------------------------

    def _parse_statement(
        self, cursor: _LineCursor, line_num: int
    ) -> ParsedStatement:
        """
        Parse a single source line into a ``ParsedStatement``.

        Strategy:
        1. If token[0] is a SYMBOL and token[1] is a mnemonic → label present.
        2. If token[0] is a mnemonic directly → no label.
        3. Otherwise → unrecognised statement.
        """
        all_tokens = list(cursor.tokens)
        t0 = cursor.current

        if t0 is None:
            return self._empty_statement(line_num)

        # --- Determine label vs no-label ---
        label: str | None = None

        if t0.type == TokenType.SYMBOL:
            # Look ahead: if next token is a mnemonic, this is a label
            t1 = cursor.peek(0 + 1)
            if t1 is not None and t1.type in (
                TokenType.DIRECTIVE,
                TokenType.IMPERATIVE,
                TokenType.DECLARATIVE,
            ):
                label = cursor.advance().value  # consume the label
            else:
                # Symbol with no following mnemonic — report error
                cursor.advance()
                return self._error_statement(
                    line_num=line_num,
                    all_tokens=all_tokens,
                    message=(
                        f"Expected a mnemonic after label '{t0.value}' "
                        f"but found {t1.type if t1 else 'end of line'}."
                    ),
                    tok=t0,
                    expected="DIRECTIVE | IMPERATIVE | DECLARATIVE",
                )

        # --- Now current token should be the mnemonic ---
        mnemonic_tok = cursor.advance()
        if mnemonic_tok is None:
            return self._error_statement(
                line_num=line_num,
                all_tokens=all_tokens,
                message="Empty statement.",
                tok=t0,
            )

        # Dispatch by token type
        if mnemonic_tok.type == TokenType.DIRECTIVE:
            return self._parse_directive(
                cursor, line_num, label, mnemonic_tok, all_tokens
            )
        if mnemonic_tok.type == TokenType.IMPERATIVE:
            return self._parse_imperative(
                cursor, line_num, label, mnemonic_tok, all_tokens
            )
        if mnemonic_tok.type == TokenType.DECLARATIVE:
            return self._parse_declarative(
                cursor, line_num, label, mnemonic_tok, all_tokens
            )

        # Unrecognised first non-label token
        return self._error_statement(
            line_num=line_num,
            all_tokens=all_tokens,
            message=(
                f"Expected a mnemonic but found '{mnemonic_tok.value}' "
                f"(type: {mnemonic_tok.type})."
            ),
            tok=mnemonic_tok,
            expected="DIRECTIVE | IMPERATIVE | DECLARATIVE",
        )

    # ------------------------------------------------------------------
    # Directive parser
    # ------------------------------------------------------------------

    def _parse_directive(
        self,
        cursor: _LineCursor,
        line_num: int,
        label: str | None,
        mnemonic_tok: Token,
        all_tokens: list[Token],
    ) -> ParsedStatement:
        mnemonic_upper = mnemonic_tok.value.upper()

        try:
            directive = Directive(mnemonic_upper)
        except ValueError:
            return self._error_statement(
                line_num=line_num,
                all_tokens=all_tokens,
                message=f"Unknown directive '{mnemonic_tok.value}'.",
                tok=mnemonic_tok,
            )

        errors: list[SyntaxError_] = []

        # --- START <NUMBER> ---
        if directive == Directive.START:
            op_tok = cursor.advance()
            trailing = cursor.remaining()

            if op_tok is None:
                errors.append(SyntaxError_(
                    message="START requires a numeric starting address.",
                    line=mnemonic_tok.line,
                    column=mnemonic_tok.column,
                    expected="NUMBER",
                ))
                return self._build(
                    line_num=line_num, label=label, directive=directive,
                    statement_class=IntermediateClass.AD,
                    all_tokens=all_tokens, errors=errors,
                )

            if op_tok.type not in _START_OP:
                errors.append(SyntaxError_(
                    message=(
                        f"START operand must be a numeric constant, "
                        f"got '{op_tok.value}' ({op_tok.type})."
                    ),
                    line=op_tok.line, column=op_tok.column,
                    token_value=op_tok.value, expected="NUMBER",
                ))

            errors += self._check_no_trailing(trailing, directive.value)
            return self._build(
                line_num=line_num, label=label, directive=directive,
                operand=op_tok.value,
                statement_class=IntermediateClass.AD,
                all_tokens=all_tokens, errors=errors,
            )

        # --- END ---
        if directive == Directive.END:
            trailing = cursor.remaining()
            errors += self._check_no_trailing(trailing, directive.value)
            return self._build(
                line_num=line_num, label=label, directive=directive,
                statement_class=IntermediateClass.AD,
                all_tokens=all_tokens, errors=errors,
            )

        # --- LTORG ---
        if directive == Directive.LTORG:
            trailing = cursor.remaining()
            errors += self._check_no_trailing(trailing, directive.value)
            return self._build(
                line_num=line_num, label=label, directive=directive,
                statement_class=IntermediateClass.AD,
                all_tokens=all_tokens, errors=errors,
            )

        # --- ORIGIN <NUMBER | SYMBOL> ---
        if directive == Directive.ORIGIN:
            op_tok = cursor.advance()
            trailing = cursor.remaining()
            if op_tok is None:
                errors.append(SyntaxError_(
                    message="ORIGIN requires an operand (address or symbol).",
                    line=mnemonic_tok.line, column=mnemonic_tok.column,
                    expected="NUMBER | SYMBOL",
                ))
                return self._build(
                    line_num=line_num, label=label, directive=directive,
                    statement_class=IntermediateClass.AD,
                    all_tokens=all_tokens, errors=errors,
                )
            if op_tok.type not in _ORIGIN_EQU_OP:
                errors.append(SyntaxError_(
                    message=(
                        f"ORIGIN operand must be a number or symbol, "
                        f"got '{op_tok.value}' ({op_tok.type})."
                    ),
                    line=op_tok.line, column=op_tok.column,
                    token_value=op_tok.value,
                    expected="NUMBER | SYMBOL",
                ))
            errors += self._check_no_trailing(trailing, directive.value)
            return self._build(
                line_num=line_num, label=label, directive=directive,
                operand=op_tok.value,
                statement_class=IntermediateClass.AD,
                all_tokens=all_tokens, errors=errors,
            )

        # --- EQU <NUMBER | SYMBOL> ---
        if directive == Directive.EQU:
            op_tok = cursor.advance()
            trailing = cursor.remaining()
            if op_tok is None:
                errors.append(SyntaxError_(
                    message="EQU requires an operand (value or symbol).",
                    line=mnemonic_tok.line, column=mnemonic_tok.column,
                    expected="NUMBER | SYMBOL",
                ))
                return self._build(
                    line_num=line_num, label=label, directive=directive,
                    statement_class=IntermediateClass.AD,
                    all_tokens=all_tokens, errors=errors,
                )
            if op_tok.type not in _ORIGIN_EQU_OP:
                errors.append(SyntaxError_(
                    message=(
                        f"EQU operand must be a number or symbol, "
                        f"got '{op_tok.value}' ({op_tok.type})."
                    ),
                    line=op_tok.line, column=op_tok.column,
                    token_value=op_tok.value,
                    expected="NUMBER | SYMBOL",
                ))
            errors += self._check_no_trailing(trailing, directive.value)
            return self._build(
                line_num=line_num, label=label, directive=directive,
                operand=op_tok.value,
                statement_class=IntermediateClass.AD,
                all_tokens=all_tokens, errors=errors,
            )

        # Should not reach here given the Directive enum is exhaustive
        return self._error_statement(
            line_num=line_num,
            all_tokens=all_tokens,
            message=f"Unhandled directive '{mnemonic_tok.value}'.",
            tok=mnemonic_tok,
        )

    # ------------------------------------------------------------------
    # Imperative parser
    # ------------------------------------------------------------------

    def _parse_imperative(
        self,
        cursor: _LineCursor,
        line_num: int,
        label: str | None,
        mnemonic_tok: Token,
        all_tokens: list[Token],
    ) -> ParsedStatement:
        mnemonic_upper = mnemonic_tok.value.upper()

        try:
            imperative = ImperativeMnemonic(mnemonic_upper)
        except ValueError:
            return self._error_statement(
                line_num=line_num, all_tokens=all_tokens,
                message=f"Unknown imperative mnemonic '{mnemonic_tok.value}'.",
                tok=mnemonic_tok,
            )

        errors: list[SyntaxError_] = []

        # --- STOP (no operands) ---
        if imperative == ImperativeMnemonic.STOP:
            trailing = cursor.remaining()
            errors += self._check_no_trailing(trailing, imperative.value)
            return self._build(
                line_num=line_num, label=label, imperative=imperative,
                statement_class=IntermediateClass.IS,
                all_tokens=all_tokens, errors=errors,
            )

        # --- READ <SYMBOL> / PRINT <SYMBOL> ---
        if imperative in (ImperativeMnemonic.READ, ImperativeMnemonic.PRINT):
            op_tok = cursor.advance()
            trailing = cursor.remaining()
            if op_tok is None:
                errors.append(SyntaxError_(
                    message=f"{imperative.value} requires a symbol operand.",
                    line=mnemonic_tok.line, column=mnemonic_tok.column,
                    expected="SYMBOL",
                ))
                return self._build(
                    line_num=line_num, label=label, imperative=imperative,
                    statement_class=IntermediateClass.IS,
                    all_tokens=all_tokens, errors=errors,
                )
            if op_tok.type not in _IO_OP1:
                errors.append(SyntaxError_(
                    message=(
                        f"{imperative.value} requires a symbol operand, "
                        f"got '{op_tok.value}' ({op_tok.type})."
                    ),
                    line=op_tok.line, column=op_tok.column,
                    token_value=op_tok.value, expected="SYMBOL",
                ))
            errors += self._check_no_trailing(trailing, imperative.value)
            return self._build(
                line_num=line_num, label=label, imperative=imperative,
                operand=op_tok.value,
                statement_class=IntermediateClass.IS,
                all_tokens=all_tokens, errors=errors,
            )

        # --- BC <CONDITION_CODE> <SYMBOL> ---
        if imperative == ImperativeMnemonic.BC:
            cc_tok = cursor.advance()
            target_tok = cursor.advance()
            trailing = cursor.remaining()

            cc_val: ConditionCode | None = None

            if cc_tok is None:
                errors.append(SyntaxError_(
                    message="BC requires a condition code and branch target.",
                    line=mnemonic_tok.line, column=mnemonic_tok.column,
                    expected="CONDITION_CODE SYMBOL",
                ))
            else:
                if cc_tok.type != TokenType.CONDITION_CODE:
                    errors.append(SyntaxError_(
                        message=(
                            f"BC first operand must be a condition code, "
                            f"got '{cc_tok.value}' ({cc_tok.type})."
                        ),
                        line=cc_tok.line, column=cc_tok.column,
                        token_value=cc_tok.value,
                        expected="CONDITION_CODE",
                    ))
                else:
                    try:
                        cc_val = ConditionCode(cc_tok.value.upper())
                    except ValueError:
                        errors.append(SyntaxError_(
                            message=f"Invalid condition code '{cc_tok.value}'.",
                            line=cc_tok.line, column=cc_tok.column,
                            token_value=cc_tok.value,
                        ))

            operand_str: str | None = None
            if target_tok is None:
                if cc_tok is not None:   # only report if CC was present
                    errors.append(SyntaxError_(
                        message="BC requires a branch target symbol.",
                        line=(cc_tok.line if cc_tok else mnemonic_tok.line),
                        column=(cc_tok.column if cc_tok else mnemonic_tok.column),
                        expected="SYMBOL",
                    ))
            else:
                if target_tok.type not in _BC_OP2:
                    errors.append(SyntaxError_(
                        message=(
                            f"BC branch target must be a symbol, "
                            f"got '{target_tok.value}' ({target_tok.type})."
                        ),
                        line=target_tok.line, column=target_tok.column,
                        token_value=target_tok.value, expected="SYMBOL",
                    ))
                else:
                    operand_str = target_tok.value

            errors += self._check_no_trailing(trailing, imperative.value)
            return self._build(
                line_num=line_num, label=label, imperative=imperative,
                condition_code=cc_val,
                operand=operand_str,
                statement_class=IntermediateClass.IS,
                all_tokens=all_tokens, errors=errors,
            )

        # --- Two-operand arithmetic:
        #     ADD SUB MULT DIV COMP → REGISTER  (REG|LIT|SYM|NUM)
        #     MOVER                 → REGISTER  (LIT|SYM|NUM)
        #     MOVEM                 → REGISTER  SYMBOL
        if imperative in (
            ImperativeMnemonic.ADD, ImperativeMnemonic.SUB,
            ImperativeMnemonic.MULT, ImperativeMnemonic.DIV,
            ImperativeMnemonic.COMP, ImperativeMnemonic.MOVER,
            ImperativeMnemonic.MOVEM,
        ):
            reg_tok = cursor.advance()
            op2_tok = cursor.advance()
            trailing = cursor.remaining()

            reg_val: Register | None = None
            operand_str = None

            # Validate first operand (register)
            if reg_tok is None:
                errors.append(SyntaxError_(
                    message=f"{imperative.value} requires a register as first operand.",
                    line=mnemonic_tok.line, column=mnemonic_tok.column,
                    expected="REGISTER",
                ))
            elif reg_tok.type != TokenType.REGISTER:
                errors.append(SyntaxError_(
                    message=(
                        f"{imperative.value} first operand must be a register, "
                        f"got '{reg_tok.value}' ({reg_tok.type})."
                    ),
                    line=reg_tok.line, column=reg_tok.column,
                    token_value=reg_tok.value, expected="REGISTER",
                ))
            else:
                try:
                    reg_val = Register(reg_tok.value.upper())
                except ValueError:
                    errors.append(SyntaxError_(
                        message=f"Invalid register name '{reg_tok.value}'.",
                        line=reg_tok.line, column=reg_tok.column,
                        token_value=reg_tok.value,
                    ))

            # Determine allowed op2 set
            if imperative == ImperativeMnemonic.MOVER:
                allowed_op2 = _MOVER_OP2
                expected_op2 = "LITERAL | SYMBOL | NUMBER"
            elif imperative == ImperativeMnemonic.MOVEM:
                allowed_op2 = _MOVEM_OP2
                expected_op2 = "SYMBOL"
            else:
                allowed_op2 = _ARITH_OP2
                expected_op2 = "REGISTER | LITERAL | SYMBOL | NUMBER"

            # Validate second operand
            if op2_tok is None:
                errors.append(SyntaxError_(
                    message=f"{imperative.value} requires a second operand.",
                    line=(reg_tok.line if reg_tok else mnemonic_tok.line),
                    column=(reg_tok.column if reg_tok else mnemonic_tok.column),
                    expected=expected_op2,
                ))
            elif op2_tok.type not in allowed_op2:
                errors.append(SyntaxError_(
                    message=(
                        f"{imperative.value} second operand must be "
                        f"{expected_op2}, got '{op2_tok.value}' ({op2_tok.type})."
                    ),
                    line=op2_tok.line, column=op2_tok.column,
                    token_value=op2_tok.value, expected=expected_op2,
                ))
            else:
                operand_str = op2_tok.value

            errors += self._check_no_trailing(trailing, imperative.value)
            return self._build(
                line_num=line_num, label=label, imperative=imperative,
                register=reg_val, operand=operand_str,
                statement_class=IntermediateClass.IS,
                all_tokens=all_tokens, errors=errors,
            )

        # Exhaustive check — all imperatives should be handled above
        return self._error_statement(
            line_num=line_num, all_tokens=all_tokens,
            message=f"Unhandled imperative '{mnemonic_tok.value}'.",
            tok=mnemonic_tok,
        )

    # ------------------------------------------------------------------
    # Declarative parser
    # ------------------------------------------------------------------

    def _parse_declarative(
        self,
        cursor: _LineCursor,
        line_num: int,
        label: str | None,
        mnemonic_tok: Token,
        all_tokens: list[Token],
    ) -> ParsedStatement:
        mnemonic_upper = mnemonic_tok.value.upper()

        try:
            declarative = DeclarativeMnemonic(mnemonic_upper)
        except ValueError:
            return self._error_statement(
                line_num=line_num, all_tokens=all_tokens,
                message=f"Unknown declarative mnemonic '{mnemonic_tok.value}'.",
                tok=mnemonic_tok,
            )

        errors: list[SyntaxError_] = []

        op_tok = cursor.advance()
        trailing = cursor.remaining()

        if op_tok is None:
            errors.append(SyntaxError_(
                message=f"{declarative.value} requires a numeric constant operand.",
                line=mnemonic_tok.line, column=mnemonic_tok.column,
                expected="NUMBER",
            ))
            return self._build(
                line_num=line_num, label=label, declarative=declarative,
                statement_class=IntermediateClass.DL,
                all_tokens=all_tokens, errors=errors,
            )

        if op_tok.type not in _DC_DS_OP:
            errors.append(SyntaxError_(
                message=(
                    f"{declarative.value} operand must be a numeric constant, "
                    f"got '{op_tok.value}' ({op_tok.type})."
                ),
                line=op_tok.line, column=op_tok.column,
                token_value=op_tok.value, expected="NUMBER",
            ))

        errors += self._check_no_trailing(trailing, declarative.value)
        return self._build(
            line_num=line_num, label=label, declarative=declarative,
            operand=op_tok.value,
            statement_class=IntermediateClass.DL,
            all_tokens=all_tokens, errors=errors,
        )

    # ------------------------------------------------------------------
    # Builder helpers
    # ------------------------------------------------------------------

    def _build(
        self,
        *,
        line_num: int,
        label: str | None = None,
        directive: Directive | None = None,
        imperative: ImperativeMnemonic | None = None,
        declarative: DeclarativeMnemonic | None = None,
        register: Register | None = None,
        condition_code: ConditionCode | None = None,
        operand: str | None = None,
        statement_class: IntermediateClass | None = None,
        all_tokens: list[Token],
        errors: list[SyntaxError_],
    ) -> ParsedStatement:
        """Construct a ``ParsedStatement`` from validated components."""
        span: SourceSpan | None = None
        if all_tokens:
            first = all_tokens[0]
            last = all_tokens[-1]
            length = (
                (last.column + (last.span.length if last.span else len(last.value)))
                - first.column
            )
            span = SourceSpan(
                line=first.line,
                column=first.column,
                length=max(1, length),
            )

        return ParsedStatement(
            line_number=line_num,
            label=label,
            directive=directive,
            imperative=imperative,
            declarative=declarative,
            register=register,
            condition_code=condition_code,
            operand=operand,
            statement_class=statement_class,
            tokens=all_tokens,
            span=span,
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def _error_statement(
        self,
        *,
        line_num: int,
        all_tokens: list[Token],
        message: str,
        tok: Token | None = None,
        expected: str | None = None,
    ) -> ParsedStatement:
        """Return a fully invalid statement with one error record."""
        err = SyntaxError_(
            message=message,
            line=tok.line if tok else line_num,
            column=tok.column if tok else 1,
            token_value=tok.value if tok else None,
            expected=expected,
        )
        return self._build(
            line_num=line_num,
            all_tokens=all_tokens,
            errors=[err],
        )

    @staticmethod
    def _empty_statement(line_num: int) -> ParsedStatement:
        return ParsedStatement(
            line_number=line_num,
            is_valid=True,
            errors=[],
        )

    @staticmethod
    def _check_no_trailing(
        trailing: list[Token], mnemonic: str
    ) -> list[SyntaxError_]:
        """Warn about unexpected extra tokens after a complete statement."""
        if not trailing:
            return []
        extra = trailing[0]
        return [
            SyntaxError_(
                message=(
                    f"Unexpected token '{extra.value}' after {mnemonic} statement."
                ),
                line=extra.line,
                column=extra.column,
                token_value=extra.value,
                expected="end of statement",
            )
        ]
