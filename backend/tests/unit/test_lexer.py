"""
Unit tests — SysForge Lexer (Phase 3).

Tests are organised to cover every requirement from the Phase 3 specification.
All tests use the real ``Lexer`` class — no mocks, no fabricated output.

Coverage checklist (mapped to spec items)
------------------------------------------
 1. Canonical demo program
 2. START directive
 3. END directive
 4. ORIGIN directive
 5. EQU directive
 6. LTORG directive
 7. All imperative mnemonics (ADD SUB MULT MOVER MOVEM COMP BC DIV READ PRINT STOP)
 8. Declarative mnemonics (DC, DS)
 9. All registers (AREG BREG CREG DREG)
10. All condition codes (LT LE EQ GT GE ANY)
11. Literals  ='5'  ='1'  ='0'  ='999'
12. Integer constants (0 1 10 100 999)
13. Symbols (LOOP RESULT NEXT SUM VAR1, identifiers with digits/underscores)
14. Mixed whitespace (multiple spaces between tokens)
15. Tabs as whitespace
16. Leading / trailing whitespace on a line
17. Source line tracking (correct line numbers)
18. Source column tracking (correct column numbers)
19. UNKNOWN tokens for unrecognised characters
20. Invalid lexical sequences (multi-character bad input)
21. Lowercase / mixed-case recognition (case-insensitive, value preserved)
22. Symbols containing digits and underscores
23. Multiple literals on one line
24. Multiple symbols on one line
25. Empty lines between statements
26. Comments (; ...) — emitted as COMMENT tokens, value includes semicolon
27. Robustness: empty input
28. Robustness: whitespace-only input
29. Robustness: very long lines
30. Robustness: CRLF line endings
31. Span (line/column/length) correctness
32. SYMBOL is never confused with a keyword
33. Unterminated literal
34. Literal with non-digit inner content
"""

from __future__ import annotations

import pytest

from engine.common.enums import TokenType
from engine.lexer import Lexer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def lex(source: str):
    """Return the token list for *source*."""
    return Lexer().analyze(source).tokens


def lex_result(source: str):
    """Return the full LexerResult for *source*."""
    return Lexer().analyze(source)


def tok(tokens, index: int):
    """Return token at *index* with a clear failure message."""
    assert index < len(tokens), (
        f"Expected token at index {index} but only {len(tokens)} tokens produced: "
        + str([(t.type, t.value) for t in tokens])
    )
    return tokens[index]


def types(tokens) -> list[str]:
    """Return the list of token type values."""
    return [t.type for t in tokens]


def values(tokens) -> list[str]:
    """Return the list of token values."""
    return [t.value for t in tokens]


# ===========================================================================
# 1. Canonical demo program
# ===========================================================================


CANONICAL = (
    "START 100\n"
    "MOVER AREG ='5'\n"
    "ADD BREG ='1'\n"
    "LOOP SUB AREG ='2'\n"
    "MOVEM AREG RESULT\n"
    "RESULT DS 1\n"
    "END"
)


class TestCanonicalProgram:
    """Full token-stream verification of the canonical SysForge demo."""

    def setup_method(self):
        self.tokens = lex(CANONICAL)

    def test_no_errors(self):
        result = lex_result(CANONICAL)
        assert result.success is True
        assert result.diagnostics == []

    def test_total_token_count(self):
        # START 100 | MOVER AREG ='5' | ADD BREG ='1' | LOOP SUB AREG ='2'
        # MOVEM AREG RESULT | RESULT DS 1 | END
        # = 2 + 3 + 3 + 4 + 3 + 3 + 1 = 19 tokens
        assert len(self.tokens) == 19

    # --- Line 1: START 100 ---
    def test_line1_start_type(self):
        assert tok(self.tokens, 0).type == TokenType.DIRECTIVE

    def test_line1_start_value(self):
        assert tok(self.tokens, 0).value == "START"

    def test_line1_start_position(self):
        t = tok(self.tokens, 0)
        assert t.line == 1
        assert t.column == 1

    def test_line1_constant_type(self):
        assert tok(self.tokens, 1).type == TokenType.NUMBER

    def test_line1_constant_value(self):
        assert tok(self.tokens, 1).value == "100"

    def test_line1_constant_position(self):
        t = tok(self.tokens, 1)
        assert t.line == 1
        assert t.column == 7

    # --- Line 2: MOVER AREG ='5' ---
    def test_line2_mover_type(self):
        assert tok(self.tokens, 2).type == TokenType.IMPERATIVE

    def test_line2_mover_value(self):
        assert tok(self.tokens, 2).value == "MOVER"

    def test_line2_mover_line(self):
        assert tok(self.tokens, 2).line == 2

    def test_line2_mover_column(self):
        assert tok(self.tokens, 2).column == 1

    def test_line2_areg_type(self):
        assert tok(self.tokens, 3).type == TokenType.REGISTER

    def test_line2_areg_value(self):
        assert tok(self.tokens, 3).value == "AREG"

    def test_line2_literal_type(self):
        assert tok(self.tokens, 4).type == TokenType.LITERAL

    def test_line2_literal_value(self):
        assert tok(self.tokens, 4).value == "='5'"

    def test_line2_literal_column(self):
        # "MOVER AREG " = 11 chars → ='5' starts at col 12
        assert tok(self.tokens, 4).column == 12

    # --- Line 3: ADD BREG ='1' ---
    def test_line3_add_type(self):
        assert tok(self.tokens, 5).type == TokenType.IMPERATIVE

    def test_line3_breg_type(self):
        assert tok(self.tokens, 6).type == TokenType.REGISTER

    def test_line3_breg_value(self):
        assert tok(self.tokens, 6).value == "BREG"

    def test_line3_literal_value(self):
        assert tok(self.tokens, 7).value == "='1'"

    # --- Line 4: LOOP SUB AREG ='2' ---
    def test_line4_loop_type(self):
        assert tok(self.tokens, 8).type == TokenType.SYMBOL

    def test_line4_loop_value(self):
        assert tok(self.tokens, 8).value == "LOOP"

    def test_line4_loop_line(self):
        assert tok(self.tokens, 8).line == 4

    def test_line4_loop_column(self):
        assert tok(self.tokens, 8).column == 1

    def test_line4_sub_type(self):
        assert tok(self.tokens, 9).type == TokenType.IMPERATIVE

    def test_line4_literal_value(self):
        assert tok(self.tokens, 11).value == "='2'"

    # --- Line 5: MOVEM AREG RESULT ---
    def test_line5_movem_type(self):
        assert tok(self.tokens, 12).type == TokenType.IMPERATIVE

    def test_line5_result_type(self):
        # RESULT is a SYMBOL when encountered as an operand
        assert tok(self.tokens, 14).type == TokenType.SYMBOL

    # --- Line 6: RESULT DS 1 ---
    def test_line6_result_symbol(self):
        assert tok(self.tokens, 15).type == TokenType.SYMBOL

    def test_line6_ds_type(self):
        assert tok(self.tokens, 16).type == TokenType.DECLARATIVE

    def test_line6_constant_type(self):
        assert tok(self.tokens, 17).type == TokenType.NUMBER

    def test_line6_constant_value(self):
        assert tok(self.tokens, 17).value == "1"

    # --- Line 7: END ---
    def test_line7_end_type(self):
        assert tok(self.tokens, 18).type == TokenType.DIRECTIVE

    def test_line7_end_value(self):
        assert tok(self.tokens, 18).value == "END"

    def test_line7_end_line(self):
        assert tok(self.tokens, 18).line == 7


# ===========================================================================
# 2–6. Directives
# ===========================================================================


class TestDirectives:
    def test_start(self):
        t = lex("START 100")[0]
        assert t.type == TokenType.DIRECTIVE
        assert t.value == "START"

    def test_end(self):
        t = lex("END")[0]
        assert t.type == TokenType.DIRECTIVE
        assert t.value == "END"

    def test_origin(self):
        t = lex("ORIGIN 200")[0]
        assert t.type == TokenType.DIRECTIVE
        assert t.value == "ORIGIN"

    def test_equ(self):
        t = lex("EQU 5")[0]
        assert t.type == TokenType.DIRECTIVE
        assert t.value == "EQU"

    def test_ltorg(self):
        t = lex("LTORG")[0]
        assert t.type == TokenType.DIRECTIVE
        assert t.value == "LTORG"

    def test_all_five_directives_recognized(self):
        for kw in ["START", "END", "ORIGIN", "EQU", "LTORG"]:
            ts = lex(kw)
            assert ts[0].type == TokenType.DIRECTIVE, f"{kw} not DIRECTIVE"


# ===========================================================================
# 7. All imperative mnemonics
# ===========================================================================


class TestImperativeMnemonics:
    IMPERATIVES = [
        "ADD", "SUB", "MULT", "MOVER", "MOVEM",
        "COMP", "BC", "DIV", "READ", "PRINT", "STOP",
    ]

    def test_all_imperatives_classified(self):
        for kw in self.IMPERATIVES:
            ts = lex(kw)
            assert ts[0].type == TokenType.IMPERATIVE, f"{kw} not IMPERATIVE"

    def test_stop_alone(self):
        ts = lex("STOP")
        assert ts[0].type == TokenType.IMPERATIVE
        assert ts[0].value == "STOP"

    def test_bc_alone(self):
        ts = lex("BC")
        assert ts[0].type == TokenType.IMPERATIVE

    def test_print_alone(self):
        ts = lex("PRINT")
        assert ts[0].type == TokenType.IMPERATIVE


# ===========================================================================
# 8. Declarative mnemonics
# ===========================================================================


class TestDeclarativeMnemonics:
    def test_dc(self):
        ts = lex("DC 5")
        assert ts[0].type == TokenType.DECLARATIVE
        assert ts[0].value == "DC"

    def test_ds(self):
        ts = lex("DS 3")
        assert ts[0].type == TokenType.DECLARATIVE
        assert ts[0].value == "DS"


# ===========================================================================
# 9. All registers
# ===========================================================================


class TestRegisters:
    def test_areg(self):
        assert lex("AREG")[0].type == TokenType.REGISTER

    def test_breg(self):
        assert lex("BREG")[0].type == TokenType.REGISTER

    def test_creg(self):
        assert lex("CREG")[0].type == TokenType.REGISTER

    def test_dreg(self):
        assert lex("DREG")[0].type == TokenType.REGISTER

    def test_all_four_registers(self):
        for reg in ["AREG", "BREG", "CREG", "DREG"]:
            assert lex(reg)[0].type == TokenType.REGISTER, f"{reg} not REGISTER"


# ===========================================================================
# 10. All condition codes
# ===========================================================================


class TestConditionCodes:
    def test_lt(self):
        assert lex("LT")[0].type == TokenType.CONDITION_CODE

    def test_le(self):
        assert lex("LE")[0].type == TokenType.CONDITION_CODE

    def test_eq(self):
        assert lex("EQ")[0].type == TokenType.CONDITION_CODE

    def test_gt(self):
        assert lex("GT")[0].type == TokenType.CONDITION_CODE

    def test_ge(self):
        assert lex("GE")[0].type == TokenType.CONDITION_CODE

    def test_any(self):
        assert lex("ANY")[0].type == TokenType.CONDITION_CODE

    def test_all_six_condition_codes(self):
        for cc in ["LT", "LE", "EQ", "GT", "GE", "ANY"]:
            assert lex(cc)[0].type == TokenType.CONDITION_CODE, f"{cc} not CONDITION_CODE"

    def test_bc_followed_by_condition_code(self):
        ts = lex("BC LT LOOP")
        assert ts[0].type == TokenType.IMPERATIVE
        assert ts[1].type == TokenType.CONDITION_CODE
        assert ts[2].type == TokenType.SYMBOL


# ===========================================================================
# 11. Literals
# ===========================================================================


class TestLiterals:
    def test_literal_5(self):
        ts = lex("='5'")
        assert ts[0].type == TokenType.LITERAL
        assert ts[0].value == "='5'"

    def test_literal_1(self):
        ts = lex("='1'")
        assert ts[0].type == TokenType.LITERAL
        assert ts[0].value == "='1'"

    def test_literal_0(self):
        ts = lex("='0'")
        assert ts[0].type == TokenType.LITERAL
        assert ts[0].value == "='0'"

    def test_literal_999(self):
        ts = lex("='999'")
        assert ts[0].type == TokenType.LITERAL
        assert ts[0].value == "='999'"

    def test_literal_value_preserved_completely(self):
        # Ensure the full ='...' form is preserved, not just the number
        ts = lex("='42'")
        assert ts[0].value == "='42'"

    def test_literal_inline_with_instruction(self):
        ts = lex("MOVER AREG ='5'")
        assert ts[2].type == TokenType.LITERAL
        assert ts[2].value == "='5'"

    def test_multiple_literals_on_one_line(self):
        # Hypothetical two-operand line with two literals
        ts = lex("='1' ='2' ='3'")
        assert types(ts) == [
            TokenType.LITERAL, TokenType.LITERAL, TokenType.LITERAL
        ]
        assert values(ts) == ["='1'", "='2'", "='3'"]


# ===========================================================================
# 12. Integer constants
# ===========================================================================


class TestConstants:
    def test_zero(self):
        ts = lex("0")
        assert ts[0].type == TokenType.NUMBER
        assert ts[0].value == "0"

    def test_single_digit(self):
        assert lex("1")[0].type == TokenType.NUMBER

    def test_two_digit(self):
        ts = lex("10")
        assert ts[0].type == TokenType.NUMBER
        assert ts[0].value == "10"

    def test_three_digit(self):
        ts = lex("100")
        assert ts[0].type == TokenType.NUMBER
        assert ts[0].value == "100"

    def test_large_constant(self):
        ts = lex("999")
        assert ts[0].value == "999"

    def test_constant_after_directive(self):
        ts = lex("START 100")
        assert ts[1].type == TokenType.NUMBER
        assert ts[1].value == "100"


# ===========================================================================
# 13. Symbols
# ===========================================================================


class TestSymbols:
    def test_loop(self):
        assert lex("LOOP")[0].type == TokenType.SYMBOL

    def test_result(self):
        assert lex("RESULT")[0].type == TokenType.SYMBOL

    def test_next(self):
        assert lex("NEXT")[0].type == TokenType.SYMBOL

    def test_sum(self):
        assert lex("SUM")[0].type == TokenType.SYMBOL

    def test_var1(self):
        ts = lex("VAR1")
        assert ts[0].type == TokenType.SYMBOL
        assert ts[0].value == "VAR1"

    def test_symbol_value_preserved(self):
        assert lex("MYVAR")[0].value == "MYVAR"

    def test_multiple_symbols(self):
        ts = lex("LOOP RESULT NEXT")
        assert all(t.type == TokenType.SYMBOL for t in ts)
        assert values(ts) == ["LOOP", "RESULT", "NEXT"]


# ===========================================================================
# 22. Symbols with digits and underscores
# ===========================================================================


class TestSymbolSyntax:
    """Valid symbol rule: starts with letter or underscore, then [A-Za-z0-9_]*"""

    def test_symbol_with_trailing_digit(self):
        # VAR1 — letter then digit
        assert lex("VAR1")[0].type == TokenType.SYMBOL

    def test_symbol_with_underscore(self):
        assert lex("MY_VAR")[0].type == TokenType.SYMBOL

    def test_symbol_with_multiple_digits(self):
        ts = lex("A123")
        assert ts[0].type == TokenType.SYMBOL

    def test_symbol_with_only_letters(self):
        assert lex("ALPHA")[0].type == TokenType.SYMBOL

    def test_digit_alone_is_not_symbol(self):
        # A bare digit is a NUMBER, not a SYMBOL
        assert lex("5")[0].type == TokenType.NUMBER

    def test_underscore_start_is_symbol(self):
        assert lex("_VAR")[0].type == TokenType.SYMBOL


# ===========================================================================
# 14 & 15. Whitespace (spaces and tabs)
# ===========================================================================


class TestWhitespace:
    def test_multiple_spaces_between_tokens(self):
        ts = lex("START    100")
        assert len(ts) == 2
        assert ts[0].value == "START"
        assert ts[1].value == "100"

    def test_tab_between_tokens(self):
        ts = lex("START\t100")
        assert len(ts) == 2
        assert ts[1].value == "100"

    def test_mixed_spaces_and_tabs(self):
        ts = lex("ADD\t AREG   BREG")
        assert len(ts) == 3

    def test_whitespace_does_not_appear_as_token(self):
        ts = lex("ADD AREG BREG")
        assert all(t.type != TokenType.UNKNOWN for t in ts)

    def test_multiple_spaces_do_not_change_token_values(self):
        # Token values are the raw word, not affected by surrounding whitespace
        ts = lex("   MOVER   AREG   ='5'   ")
        assert values(ts) == ["MOVER", "AREG", "='5'"]


# ===========================================================================
# 16. Leading / trailing whitespace
# ===========================================================================


class TestLeadingTrailingWhitespace:
    def test_leading_spaces(self):
        ts = lex("   START 100")
        assert ts[0].type == TokenType.DIRECTIVE
        assert ts[0].column == 4   # 3 spaces → token at col 4

    def test_trailing_spaces(self):
        ts = lex("START 100   ")
        assert len(ts) == 2        # no extra tokens from trailing spaces

    def test_leading_tab(self):
        ts = lex("\tSTART 100")
        assert ts[0].type == TokenType.DIRECTIVE


# ===========================================================================
# 17. Source line tracking
# ===========================================================================


class TestLineTracking:
    def test_line1_token_is_on_line1(self):
        ts = lex("START 100\nEND")
        assert ts[0].line == 1

    def test_line2_token_is_on_line2(self):
        ts = lex("START 100\nEND")
        assert ts[2].line == 2

    def test_three_lines(self):
        ts = lex("A\nB\nC")
        assert ts[0].line == 1
        assert ts[1].line == 2
        assert ts[2].line == 3

    def test_empty_lines_advance_line_counter(self):
        ts = lex("START\n\nEND")
        assert ts[0].line == 1
        assert ts[1].line == 3   # blank line 2 skipped

    def test_canonical_last_token_on_correct_line(self):
        ts = lex(CANONICAL)
        assert ts[-1].line == 7   # END is on line 7


# ===========================================================================
# 18. Source column tracking
# ===========================================================================


class TestColumnTracking:
    def test_first_token_col1(self):
        assert lex("MOVER AREG")[0].column == 1

    def test_second_token_after_space(self):
        ts = lex("ADD BREG")
        assert ts[1].column == 5   # "ADD " = 4 chars → BREG starts at 5

    def test_literal_column_in_three_token_line(self):
        # "MOVER AREG ='5'"
        # M=1 O=2 V=3 E=4 R=5 space=6 A=7 R=8 E=9 G=10 space=11 =12
        ts = lex("MOVER AREG ='5'")
        assert ts[2].column == 12

    def test_column_resets_on_new_line(self):
        ts = lex("START 100\nEND")
        # END is the 3rd token; should be at col 1 of line 2
        assert ts[2].column == 1

    def test_leading_spaces_offset_column(self):
        ts = lex("   END")
        assert ts[0].column == 4

    def test_tab_counts_as_one_column(self):
        ts = lex("\tEND")
        assert ts[0].column == 2   # one tab = one column advance

    def test_span_length_matches_value(self):
        ts = lex("MOVER")
        assert ts[0].span is not None
        assert ts[0].span.length == len("MOVER")

    def test_literal_span_length(self):
        ts = lex("='999'")
        assert ts[0].span.length == len("='999'")


# ===========================================================================
# 19 & 20. Unknown / invalid tokens
# ===========================================================================


class TestUnknownTokens:
    def test_at_sign_produces_unknown(self):
        ts = lex("@")
        assert ts[0].type == TokenType.UNKNOWN

    def test_hash_produces_unknown(self):
        ts = lex("#")
        assert ts[0].type == TokenType.UNKNOWN

    def test_unknown_char_records_diagnostic(self):
        result = lex_result("@LOOP")
        # '@' is UNKNOWN, 'LOOP' is SYMBOL
        assert any(t.type == TokenType.UNKNOWN for t in result.tokens)
        assert len(result.diagnostics) >= 1

    def test_unknown_char_does_not_abort_stream(self):
        ts = lex("MOVER @ AREG")
        type_list = types(ts)
        # Must still see MOVER and AREG
        assert TokenType.IMPERATIVE in type_list
        assert TokenType.REGISTER in type_list

    def test_unknown_char_severity_is_error(self):
        result = lex_result("@")
        assert result.success is False
        assert result.diagnostics[0]["severity"] == "ERROR"

    def test_dollar_produces_unknown(self):
        ts = lex("$VAR")
        assert ts[0].type == TokenType.UNKNOWN

    def test_multiple_unknown_chars(self):
        result = lex_result("@ # $")
        unknown_count = sum(1 for t in result.tokens if t.type == TokenType.UNKNOWN)
        assert unknown_count == 3
        assert len(result.diagnostics) == 3


# ===========================================================================
# 21. Case handling
# ===========================================================================


class TestCaseHandling:
    """Reserved-word recognition is case-insensitive; value preserves spelling."""

    def test_lowercase_mover_is_imperative(self):
        t = lex("mover")[0]
        assert t.type == TokenType.IMPERATIVE

    def test_lowercase_mover_value_preserved(self):
        t = lex("mover")[0]
        assert t.value == "mover"   # NOT normalised to "MOVER"

    def test_mixedcase_mover(self):
        t = lex("Mover")[0]
        assert t.type == TokenType.IMPERATIVE
        assert t.value == "Mover"

    def test_lowercase_start_directive(self):
        t = lex("start")[0]
        assert t.type == TokenType.DIRECTIVE
        assert t.value == "start"

    def test_lowercase_areg_register(self):
        t = lex("areg")[0]
        assert t.type == TokenType.REGISTER
        assert t.value == "areg"

    def test_lowercase_lt_condition_code(self):
        t = lex("lt")[0]
        assert t.type == TokenType.CONDITION_CODE
        assert t.value == "lt"

    def test_lowercase_dc(self):
        t = lex("dc")[0]
        assert t.type == TokenType.DECLARATIVE
        assert t.value == "dc"

    def test_uppercase_always_recognised(self):
        for kw in ["MOVER", "START", "AREG", "LT", "DC"]:
            ts = lex(kw)
            assert ts[0].type != TokenType.SYMBOL, f"{kw} should not be SYMBOL"


# ===========================================================================
# 25. Empty lines
# ===========================================================================


class TestEmptyLines:
    def test_empty_string_produces_no_tokens(self):
        assert lex("") == []

    def test_whitespace_only_produces_no_tokens(self):
        assert lex("   \t  ") == []

    def test_blank_line_between_statements(self):
        ts = lex("START 100\n\nEND")
        assert len(ts) == 3

    def test_multiple_blank_lines(self):
        ts = lex("\n\n\nSTART\n\n\nEND\n\n")
        assert len(ts) == 2
        assert ts[0].type == TokenType.DIRECTIVE
        assert ts[1].type == TokenType.DIRECTIVE


# ===========================================================================
# 26. Comments
# ===========================================================================


class TestComments:
    def test_comment_token_type(self):
        ts = lex("; this is a comment")
        assert ts[0].type == TokenType.COMMENT

    def test_comment_value_includes_semicolon(self):
        ts = lex("; hello")
        assert ts[0].value.startswith(";")

    def test_comment_after_instruction(self):
        ts = lex("STOP ; halt the machine")
        assert ts[0].type == TokenType.IMPERATIVE
        assert ts[1].type == TokenType.COMMENT

    def test_comment_does_not_capture_next_line(self):
        ts = lex("; line one comment\nSTART 100")
        assert ts[0].type == TokenType.COMMENT
        assert ts[1].type == TokenType.DIRECTIVE
        assert ts[1].line == 2

    def test_comment_only_line(self):
        result = lex_result("; just a comment\nEND")
        assert result.success is True

    def test_comment_counted_separately_from_token_count(self):
        # token_count excludes COMMENT tokens
        result = lex_result("STOP ; comment\nEND")
        assert result.token_count == 2   # STOP + END, not the comment


# ===========================================================================
# 27–30. Robustness tests
# ===========================================================================


class TestRobustness:
    def test_empty_input(self):
        result = lex_result("")
        assert result.tokens == []
        assert result.success is True
        assert result.token_count == 0

    def test_whitespace_only_input(self):
        result = lex_result("   \t\n\n  ")
        assert result.tokens == []
        assert result.success is True

    def test_very_long_line(self):
        # 500 space-separated tokens — must not crash
        long_line = " ".join(["LOOP"] * 500)
        result = lex_result(long_line)
        assert len(result.tokens) == 500
        assert all(t.type == TokenType.SYMBOL for t in result.tokens)

    def test_crlf_line_endings(self):
        ts = lex("START 100\r\nEND")
        assert ts[0].value == "START"
        assert ts[2].value == "END"
        assert ts[2].line == 2

    def test_crlf_column_resets(self):
        ts = lex("A\r\nB")
        assert ts[1].column == 1

    def test_malformed_input_does_not_raise(self):
        # Nasty mix of bad characters
        result = lex_result("@@@ ### $$$ STOP")
        assert any(t.type == TokenType.IMPERATIVE for t in result.tokens)

    def test_single_character_programs(self):
        for src in ["A", "1", ";"]:
            result = lex_result(src)
            assert len(result.tokens) >= 1


# ===========================================================================
# 31. Span correctness
# ===========================================================================


class TestSpans:
    def test_span_line_matches_token_line(self):
        ts = lex("MOVER")
        assert ts[0].span.line == ts[0].line

    def test_span_column_matches_token_column(self):
        ts = lex("  AREG")
        assert ts[0].span.column == ts[0].column

    def test_directive_span_length(self):
        ts = lex("START")
        assert ts[0].span.length == 5

    def test_number_span_length(self):
        ts = lex("100")
        assert ts[0].span.length == 3

    def test_symbol_span_length(self):
        ts = lex("LOOP")
        assert ts[0].span.length == 4


# ===========================================================================
# 33. Unterminated literal
# ===========================================================================


class TestUnterminatedLiteral:
    def test_unterminated_literal_produces_unknown(self):
        ts = lex("='5")
        assert ts[0].type == TokenType.UNKNOWN

    def test_unterminated_literal_records_diagnostic(self):
        result = lex_result("='5")
        assert result.success is False
        assert len(result.diagnostics) >= 1
        assert result.diagnostics[0]["code"] == "UNTERMINATED_LITERAL"

    def test_scanner_continues_after_unterminated_literal(self):
        # Even after a bad literal, END should be tokenised
        ts = lex("='5\nEND")
        assert any(t.value == "END" for t in ts)


# ===========================================================================
# 34. Invalid literal format (non-digit inner content)
# ===========================================================================


class TestInvalidLiteralFormat:
    def test_literal_with_letter_content_is_unknown(self):
        ts = lex("='ABC'")
        assert ts[0].type == TokenType.UNKNOWN

    def test_literal_with_letter_content_records_diagnostic(self):
        result = lex_result("='ABC'")
        assert result.success is False
        assert any(d["code"] == "INVALID_LITERAL_FORMAT" for d in result.diagnostics)


# ===========================================================================
# 32. SYMBOL is never a keyword
# ===========================================================================


class TestSymbolKeywordBoundary:
    """Identifiers that start with a keyword prefix but are not keywords
    must be classified as SYMBOL, not as the partial keyword."""

    def test_adder_is_symbol_not_imperative(self):
        # "ADDER" starts with "ADD" but is not in IMPERATIVE_KEYWORDS
        assert lex("ADDER")[0].type == TokenType.SYMBOL

    def test_starter_is_symbol_not_directive(self):
        assert lex("STARTER")[0].type == TokenType.SYMBOL

    def test_bcx_is_symbol_not_imperative(self):
        assert lex("BCX")[0].type == TokenType.SYMBOL

    def test_subtotal_is_symbol(self):
        assert lex("SUBTOTAL")[0].type == TokenType.SYMBOL

    def test_stops_is_symbol(self):
        # "STOPS" starts with "STOP" but is not a keyword
        assert lex("STOPS")[0].type == TokenType.SYMBOL


# ===========================================================================
# token_count field
# ===========================================================================


class TestTokenCount:
    def test_count_excludes_comments(self):
        result = lex_result("ADD AREG BREG ; comment")
        assert result.token_count == 3

    def test_count_matches_non_comment_tokens(self):
        result = lex_result(CANONICAL)
        non_comment = [t for t in result.tokens if t.type != TokenType.COMMENT]
        assert result.token_count == len(non_comment)

    def test_empty_source_count_zero(self):
        assert lex_result("").token_count == 0


# ===========================================================================
# LexerResult.success field
# ===========================================================================


class TestLexerResultSuccess:
    def test_clean_source_is_success(self):
        assert lex_result(CANONICAL).success is True

    def test_unknown_char_sets_success_false(self):
        assert lex_result("@").success is False

    def test_unterminated_literal_sets_success_false(self):
        assert lex_result("='5").success is False
