"""
SysForge — Deterministic Lexical Analyzer (Lexer).

Converts raw educational assembly source text into a structured stream of
``Token`` objects.  This is Phase 3 of the SysForge toolchain.

==========================================================================
Language specification handled here
==========================================================================

Directives   : START  END  ORIGIN  EQU  LTORG
Imperatives  : ADD  SUB  MULT  MOVER  MOVEM  COMP  BC  DIV  READ  PRINT  STOP
Declaratives : DC  DS
Registers    : AREG  BREG  CREG  DREG
Condition    : LT  LE  EQ  GT  GE  ANY
Literals     : ='<integer>'   e.g.  ='5'  ='1'  ='2'
Constants    : decimal integers   e.g.  0  1  100  999
Symbols      : identifier matching  [A-Za-z][A-Za-z0-9_]*
Comments     : semicolon (;) to end of line

==========================================================================
Lexer behaviour contract
==========================================================================

Case policy
-----------
Reserved-word recognition is CASE-INSENSITIVE.  The token ``value``
always preserves the ORIGINAL source spelling.

  source: "mover"  →  type=IMPERATIVE, value="mover"
  source: "MOVER"  →  type=IMPERATIVE, value="MOVER"
  source: "Mover"  →  type=IMPERATIVE, value="Mover"

Normalised uppercase is available via ``token.value.upper()``.

Whitespace
----------
Spaces and tabs separate tokens; they do not become tokens themselves.
Column numbers are tracked per character so multi-space gaps do not
affect the column reported for the next token.

Comments
--------
A semicolon (;) starts a comment running to end-of-line.
Comments are emitted as a COMMENT token (the full text including ;).
They are NOT forwarded to the parser.

Source positions
----------------
• Lines   : 1-based, incremented on each ``\\n``.
• Columns : 1-based, reset to 1 at the start of every line.
• Each token records the column of its FIRST character.
• The ``span`` field carries (line, column, length) for precise highlighting.

Error handling
--------------
Unrecognised characters produce an UNKNOWN token and an EngineDiagnostic
with severity ERROR.  The scanner continues past the bad character — it
never raises an exception or aborts the token stream.

Lexer responsibility boundary
------------------------------
The lexer identifies WHAT a token is, not WHAT ROLE it plays:
  - "LOOP"   is a SYMBOL   (not a "label" — that is the parser's job)
  - "123"    is a NUMBER    (not "the START address" — that is Pass-I)
  - "='5'"   is a LITERAL   (not "pool entry #0" — that is Pass-I)
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from app.models.tokens import LexerResult, SourceSpan, Token
from engine.common.enums import (
    CONDITION_CODE_KEYWORDS,
    DECLARATIVE_KEYWORDS,
    DIRECTIVE_KEYWORDS,
    IMPERATIVE_KEYWORDS,
    REGISTER_KEYWORDS,
    AnalysisStage,
    TokenType,
)
from engine.common.errors import DiagnosticBag, EngineDiagnostic

# ---------------------------------------------------------------------------
# Internal scanner state (private)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _ScanState:
    """Mutable cursor state during a single scan pass."""

    source: str
    pos: int = 0       # current character index into source
    line: int = 1      # current 1-based line number
    col: int = 1       # current 1-based column number

    @property
    def at_end(self) -> bool:
        return self.pos >= len(self.source)

    @property
    def current(self) -> str:
        """Return the character at the current position, or '' at EOF."""
        return self.source[self.pos] if not self.at_end else ""

    def peek(self, offset: int = 1) -> str:
        """Return the character offset positions ahead, or '' past EOF."""
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ""

    def advance(self) -> str:
        """
        Consume the current character, update line/column tracking, and
        return the consumed character.
        """
        ch = self.current
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def advance_n(self, n: int) -> str:
        """Consume exactly *n* characters and return the consumed string."""
        consumed = []
        for _ in range(n):
            consumed.append(self.advance())
        return "".join(consumed)

    def snapshot(self) -> tuple[int, int]:
        """Return (line, col) at the current position."""
        return (self.line, self.col)


# ---------------------------------------------------------------------------
# Keyword classification helper
# ---------------------------------------------------------------------------

def _classify_word(upper: str) -> TokenType:
    """
    Map an uppercase word to its ``TokenType``.

    Classification order matters: directives and imperatives share no
    overlap, but if a future keyword were added to both sets the first
    matching test would win.
    """
    if upper in DIRECTIVE_KEYWORDS:
        return TokenType.DIRECTIVE
    if upper in IMPERATIVE_KEYWORDS:
        return TokenType.IMPERATIVE
    if upper in DECLARATIVE_KEYWORDS:
        return TokenType.DECLARATIVE
    if upper in REGISTER_KEYWORDS:
        return TokenType.REGISTER
    if upper in CONDITION_CODE_KEYWORDS:
        return TokenType.CONDITION_CODE
    return TokenType.SYMBOL


# ---------------------------------------------------------------------------
# Main Lexer class
# ---------------------------------------------------------------------------


class Lexer:
    """
    SysForge deterministic lexical analyzer.

    Usage::

        from engine.lexer import Lexer

        lexer = Lexer()
        result = lexer.analyze("START 100\\nMOVER AREG ='5'\\nEND")
        for token in result.tokens:
            print(token)

    The ``Lexer`` instance is stateless between calls — ``analyze()`` can
    be called multiple times safely.
    """

    # Maximum source size accepted by the lexer (safety guard).
    MAX_SOURCE_CHARS: int = 64_000

    def analyze(self, source: str) -> LexerResult:
        """
        Tokenise *source* and return a ``LexerResult``.

        Args:
            source: Raw educational assembly source text (may be multi-line).

        Returns:
            ``LexerResult`` with:
              - ``tokens``       — ordered list of ``Token`` objects
              - ``diagnostics``  — list of serialised ``EngineDiagnostic``
              - ``success``      — ``False`` if any UNKNOWN tokens were produced
              - ``token_count``  — number of tokens (excluding COMMENT tokens)
        """
        if not source or not source.strip():
            return LexerResult(tokens=[], diagnostics=[], success=True, token_count=0)

        # Safety truncation — prevents runaway scans on huge inputs
        if len(source) > self.MAX_SOURCE_CHARS:
            source = source[: self.MAX_SOURCE_CHARS]

        state = _ScanState(source=source)
        tokens: list[Token] = []
        bag = DiagnosticBag()

        while not state.at_end:
            tok = self._next_token(state, bag)
            if tok is not None:
                tokens.append(tok)

        # Build result
        has_errors = bag.has_errors
        non_comment_count = sum(
            1 for t in tokens if t.type not in (TokenType.COMMENT,)
        )
        diagnostics = [dataclasses.asdict(d) for d in bag.items]

        return LexerResult(
            tokens=tokens,
            diagnostics=diagnostics,
            success=not has_errors,
            token_count=non_comment_count,
        )

    # ------------------------------------------------------------------
    # Core scanner — returns one token per call, advances state
    # ------------------------------------------------------------------

    def _next_token(
        self, state: _ScanState, bag: DiagnosticBag
    ) -> Token | None:
        """
        Scan the next token from *state*.

        Returns ``None`` for whitespace (consumed and discarded).
        Returns a ``Token`` for everything else.
        """
        ch = state.current

        # --- Whitespace (space / tab) — skip, no token emitted ---
        if ch in (" ", "\t"):
            state.advance()
            return None

        # --- Newline — skip; line/col tracking handled by advance() ---
        if ch == "\n" or ch == "\r":
            if ch == "\r" and state.peek() == "\n":
                state.advance()  # consume CR in CRLF
            state.advance()      # consume LF (or lone CR)
            return None

        # --- Comment: ; ... to end of line ---
        if ch == ";":
            return self._scan_comment(state)

        # --- Literal: ='...' ---
        if ch == "=" and state.peek() == "'":
            return self._scan_literal(state, bag)

        # --- Number: decimal integer ---
        if ch.isdigit():
            return self._scan_number(state)

        # --- Word: keyword or symbol ---
        if ch.isalpha() or ch == "_":
            return self._scan_word(state)

        # --- Unknown character ---
        return self._scan_unknown(state, bag)

    # ------------------------------------------------------------------
    # Individual token scanners
    # ------------------------------------------------------------------

    def _scan_comment(self, state: _ScanState) -> Token:
        """Scan ';' to end-of-line (exclusive of the newline)."""
        start_line, start_col = state.snapshot()
        buf: list[str] = []
        while not state.at_end and state.current not in ("\n", "\r"):
            buf.append(state.advance())
        value = "".join(buf)
        return Token(
            type=TokenType.COMMENT,
            value=value,
            line=start_line,
            column=start_col,
            span=SourceSpan(line=start_line, column=start_col, length=len(value)),
        )

    def _scan_literal(self, state: _ScanState, bag: DiagnosticBag) -> Token:
        """
        Scan a literal of the form  ='<integer>'

        The full text including the =' and trailing ' is the token value.
        On malformed input (e.g. unterminated quote, non-digit content)
        we emit an UNKNOWN token and record a diagnostic.
        """
        start_line, start_col = state.snapshot()
        buf: list[str] = []

        # Consume  ='
        buf.append(state.advance())   # '='
        buf.append(state.advance())   # "'"

        # Consume digits (or any non-quote chars) up to closing '
        found_close = False
        while not state.at_end and state.current not in ("\n", "\r"):
            c = state.advance()
            buf.append(c)
            if c == "'":
                found_close = True
                break

        value = "".join(buf)

        if not found_close:
            bag.add_error(
                stage=AnalysisStage.LEXICAL,
                message=f"Unterminated literal '{value}' at line {start_line}, col {start_col}.",
                code="UNTERMINATED_LITERAL",
                line=start_line,
                column=start_col,
                token_value=value,
            )
            return Token(
                type=TokenType.UNKNOWN,
                value=value,
                line=start_line,
                column=start_col,
                span=SourceSpan(line=start_line, column=start_col, length=len(value)),
            )

        # Validate: content between quotes should be digits only
        inner = value[2:-1]  # strip =' and closing '
        if not inner.lstrip("-").isdigit():
            bag.add_error(
                stage=AnalysisStage.LEXICAL,
                message=(
                    f"Invalid literal content '{inner}' at line {start_line}, "
                    f"col {start_col}. Expected integer digits."
                ),
                code="INVALID_LITERAL_FORMAT",
                line=start_line,
                column=start_col,
                token_value=value,
            )
            return Token(
                type=TokenType.UNKNOWN,
                value=value,
                line=start_line,
                column=start_col,
                span=SourceSpan(line=start_line, column=start_col, length=len(value)),
            )

        return Token(
            type=TokenType.LITERAL,
            value=value,
            line=start_line,
            column=start_col,
            span=SourceSpan(line=start_line, column=start_col, length=len(value)),
        )

    def _scan_number(self, state: _ScanState) -> Token:
        """Scan a decimal integer constant."""
        start_line, start_col = state.snapshot()
        buf: list[str] = []
        while not state.at_end and state.current.isdigit():
            buf.append(state.advance())
        value = "".join(buf)
        return Token(
            type=TokenType.NUMBER,
            value=value,
            line=start_line,
            column=start_col,
            span=SourceSpan(line=start_line, column=start_col, length=len(value)),
        )

    def _scan_word(self, state: _ScanState) -> Token:
        """
        Scan an identifier (keyword or symbol).

        Valid characters: letters, digits, underscore.
        First character: letter or underscore (already guaranteed by caller).

        Classification is case-insensitive against the keyword tables;
        the token value preserves original source spelling.
        """
        start_line, start_col = state.snapshot()
        buf: list[str] = []
        while not state.at_end and (
            state.current.isalnum() or state.current == "_"
        ):
            buf.append(state.advance())
        value = "".join(buf)
        token_type = _classify_word(value.upper())
        return Token(
            type=token_type,
            value=value,
            line=start_line,
            column=start_col,
            span=SourceSpan(line=start_line, column=start_col, length=len(value)),
        )

    def _scan_unknown(
        self, state: _ScanState, bag: DiagnosticBag
    ) -> Token:
        """
        Consume one character as an UNKNOWN token and record a diagnostic.

        This is the error-recovery path — the scanner always continues.
        """
        start_line, start_col = state.snapshot()
        ch = state.advance()
        bag.add_error(
            stage=AnalysisStage.LEXICAL,
            message=(
                f"Unexpected character '{ch}' at line {start_line}, col {start_col}."
            ),
            code="INVALID_CHARACTER",
            line=start_line,
            column=start_col,
            token_value=ch,
        )
        return Token(
            type=TokenType.UNKNOWN,
            value=ch,
            line=start_line,
            column=start_col,
            span=SourceSpan(line=start_line, column=start_col, length=1),
        )
