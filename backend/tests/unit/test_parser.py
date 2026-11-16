"""
Unit tests — SysForge Parser (Phase 4).

All tests call the real ``Parser`` via the real ``Lexer``.
No mocks.  No fabricated LexerResults.

Coverage checklist (Phase 4 specification items)
-------------------------------------------------
 1. START directive
 2. END directive
 3. ORIGIN directive
 4. EQU directive
 5. LTORG directive
 6. ADD instruction
 7. SUB instruction
 8. MULT instruction
 9. MOVER instruction
10. MOVEM instruction
11. COMP instruction
12. BC instruction
13. DIV instruction
14. READ instruction
15. PRINT instruction
16. STOP instruction
17. DC declarative
18. DS declarative
19. Label + instruction
20. Instruction without label
21. Register operand correctly identified
22. Literal operand correctly identified
23. Symbol operand correctly identified
24. Constant (NUMBER) operand correctly identified
25. Condition code correctly identified
26. Wrong operand count (too many)
27. Missing operand
28. Invalid operand type
29. Invalid register (XREG etc.)
30. Invalid condition code
31. Comment tokens ignored by grammar
32. Empty lines produce no statements
33. Multiple statements
34. Error recovery across bad lines
35. Exact error location (line + column)
36. Undefined symbol is NOT a syntax error
37. Duplicate symbol is NOT a parser error
38. Canonical demo program — full verification
"""

from __future__ import annotations

import pytest

from engine.common.enums import (
    ConditionCode,
    DeclarativeMnemonic,
    Directive,
    ImperativeMnemonic,
    IntermediateClass,
    Register,
)
from engine.lexer import Lexer
from engine.parser import Parser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_lexer = Lexer()
_parser = Parser()


def parse(source: str):
    """Lex + parse *source* and return the SyntaxResult."""
    return _parser.parse(_lexer.analyze(source))


def stmts(source: str):
    """Return the statement list for *source*."""
    return parse(source).statements


def stmt(source: str, index: int = 0):
    """Return the statement at *index* from *source*."""
    result = stmts(source)
    assert index < len(result), (
        f"Expected statement at index {index} but only {len(result)} parsed: "
        + str([(s.directive or s.imperative or s.declarative, s.label) for s in result])
    )
    return result[index]


# ===========================================================================
# 1. START directive
# ===========================================================================


class TestStart:
    def test_start_directive_field(self):
        s = stmt("START 100")
        assert s.directive == Directive.START

    def test_start_operand(self):
        s = stmt("START 100")
        assert s.operand == "100"

    def test_start_class_is_ad(self):
        s = stmt("START 100")
        assert s.statement_class == IntermediateClass.AD

    def test_start_no_label(self):
        s = stmt("START 100")
        assert s.label is None

    def test_start_is_valid(self):
        assert stmt("START 100").is_valid is True

    def test_start_missing_operand_is_invalid(self):
        s = stmt("START")
        assert s.is_valid is False
        assert len(s.errors) >= 1

    def test_start_wrong_operand_type_is_invalid(self):
        # START requires a NUMBER, not a SYMBOL
        s = stmt("START LOOP")
        assert s.is_valid is False

    def test_start_line_number(self):
        s = stmt("START 100")
        assert s.line_number == 1


# ===========================================================================
# 2. END directive
# ===========================================================================


class TestEnd:
    def test_end_directive_field(self):
        s = stmt("END")
        assert s.directive == Directive.END

    def test_end_is_valid(self):
        assert stmt("END").is_valid is True

    def test_end_no_operand(self):
        s = stmt("END")
        assert s.operand is None

    def test_end_class_is_ad(self):
        assert stmt("END").statement_class == IntermediateClass.AD

    def test_end_with_trailing_token_is_invalid(self):
        s = stmt("END EXTRA")
        assert s.is_valid is False


# ===========================================================================
# 3. ORIGIN directive
# ===========================================================================


class TestOrigin:
    def test_origin_with_number(self):
        s = stmt("ORIGIN 200")
        assert s.directive == Directive.ORIGIN
        assert s.operand == "200"
        assert s.is_valid is True

    def test_origin_with_symbol(self):
        s = stmt("ORIGIN LOOP")
        assert s.directive == Directive.ORIGIN
        assert s.operand == "LOOP"
        assert s.is_valid is True

    def test_origin_missing_operand(self):
        s = stmt("ORIGIN")
        assert s.is_valid is False

    def test_origin_class_is_ad(self):
        assert stmt("ORIGIN 200").statement_class == IntermediateClass.AD


# ===========================================================================
# 4. EQU directive
# ===========================================================================


class TestEqu:
    def test_equ_with_number(self):
        s = stmt("EQU 5")
        assert s.directive == Directive.EQU
        assert s.operand == "5"
        assert s.is_valid is True

    def test_equ_with_symbol(self):
        s = stmt("EQU RESULT")
        assert s.directive == Directive.EQU
        assert s.operand == "RESULT"
        assert s.is_valid is True

    def test_equ_missing_operand(self):
        s = stmt("EQU")
        assert s.is_valid is False

    def test_equ_class_is_ad(self):
        assert stmt("EQU 5").statement_class == IntermediateClass.AD


# ===========================================================================
# 5. LTORG directive
# ===========================================================================


class TestLtorg:
    def test_ltorg_is_valid(self):
        s = stmt("LTORG")
        assert s.directive == Directive.LTORG
        assert s.is_valid is True

    def test_ltorg_no_operand(self):
        assert stmt("LTORG").operand is None

    def test_ltorg_class_is_ad(self):
        assert stmt("LTORG").statement_class == IntermediateClass.AD

    def test_ltorg_with_trailing_token_is_invalid(self):
        s = stmt("LTORG EXTRA")
        assert s.is_valid is False


# ===========================================================================
# 6–13. Imperative two-operand instructions
# ===========================================================================


class TestArithmeticInstructions:
    """ADD, SUB, MULT, COMP, DIV — REGISTER + (REG|LIT|SYM|NUM)"""

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_register_literal(self, mnemonic):
        s = stmt(f"{mnemonic} AREG ='5'")
        assert s.imperative == ImperativeMnemonic(mnemonic)
        assert s.register == Register.AREG
        assert s.operand == "='5'"
        assert s.is_valid is True

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_register_symbol(self, mnemonic):
        s = stmt(f"{mnemonic} BREG RESULT")
        assert s.register == Register.BREG
        assert s.operand == "RESULT"
        assert s.is_valid is True

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_register_constant(self, mnemonic):
        s = stmt(f"{mnemonic} CREG 10")
        assert s.register == Register.CREG
        assert s.operand == "10"
        assert s.is_valid is True

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_register_register(self, mnemonic):
        s = stmt(f"{mnemonic} AREG BREG")
        assert s.register == Register.AREG
        assert s.operand == "BREG"
        assert s.is_valid is True

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_class_is_is(self, mnemonic):
        assert stmt(f"{mnemonic} AREG BREG").statement_class == IntermediateClass.IS

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_missing_second_operand(self, mnemonic):
        s = stmt(f"{mnemonic} AREG")
        assert s.is_valid is False

    @pytest.mark.parametrize("mnemonic", ["ADD", "SUB", "MULT", "COMP", "DIV"])
    def test_arith_missing_first_operand(self, mnemonic):
        s = stmt(f"{mnemonic}")
        assert s.is_valid is False


# ===========================================================================
# 9. MOVER
# ===========================================================================


class TestMover:
    def test_mover_register_literal(self):
        s = stmt("MOVER AREG ='5'")
        assert s.imperative == ImperativeMnemonic.MOVER
        assert s.register == Register.AREG
        assert s.operand == "='5'"
        assert s.is_valid is True

    def test_mover_register_symbol(self):
        s = stmt("MOVER BREG RESULT")
        assert s.register == Register.BREG
        assert s.operand == "RESULT"
        assert s.is_valid is True

    def test_mover_register_constant(self):
        s = stmt("MOVER CREG 100")
        assert s.operand == "100"
        assert s.is_valid is True

    def test_mover_register_register_is_invalid(self):
        # MOVER cannot load a register from a register — that's ADD/MOVEM
        s = stmt("MOVER AREG BREG")
        assert s.is_valid is False

    def test_mover_class_is_is(self):
        assert stmt("MOVER AREG ='5'").statement_class == IntermediateClass.IS

    def test_mover_missing_operand(self):
        s = stmt("MOVER AREG")
        assert s.is_valid is False


# ===========================================================================
# 10. MOVEM
# ===========================================================================


class TestMovem:
    def test_movem_register_symbol(self):
        s = stmt("MOVEM AREG RESULT")
        assert s.imperative == ImperativeMnemonic.MOVEM
        assert s.register == Register.AREG
        assert s.operand == "RESULT"
        assert s.is_valid is True

    def test_movem_register_literal_is_invalid(self):
        # MOVEM must store to a memory symbol, not a literal
        s = stmt("MOVEM AREG ='5'")
        assert s.is_valid is False

    def test_movem_register_constant_is_invalid(self):
        s = stmt("MOVEM AREG 100")
        assert s.is_valid is False

    def test_movem_class_is_is(self):
        assert stmt("MOVEM AREG RESULT").statement_class == IntermediateClass.IS


# ===========================================================================
# 12. BC
# ===========================================================================


class TestBc:
    def test_bc_condition_symbol(self):
        s = stmt("BC LT LOOP")
        assert s.imperative == ImperativeMnemonic.BC
        assert s.condition_code == ConditionCode.LT
        assert s.operand == "LOOP"
        assert s.is_valid is True

    def test_bc_all_condition_codes(self):
        for cc in ["LT", "LE", "EQ", "GT", "GE", "ANY"]:
            s = stmt(f"BC {cc} LOOP")
            assert s.is_valid is True
            assert s.condition_code == ConditionCode(cc)

    def test_bc_class_is_is(self):
        assert stmt("BC EQ NEXT").statement_class == IntermediateClass.IS

    def test_bc_missing_condition_code_is_invalid(self):
        s = stmt("BC LOOP")
        # LOOP is a SYMBOL not a CONDITION_CODE
        assert s.is_valid is False

    def test_bc_missing_target_is_invalid(self):
        s = stmt("BC LT")
        assert s.is_valid is False

    def test_bc_invalid_condition_code_is_invalid(self):
        # NE is not a valid SysForge condition code
        s = stmt("BC NE LOOP")
        assert s.is_valid is False

    def test_bc_no_label(self):
        s = stmt("BC LT LOOP")
        assert s.label is None


# ===========================================================================
# 14. READ
# ===========================================================================


class TestRead:
    def test_read_symbol(self):
        s = stmt("READ NUM")
        assert s.imperative == ImperativeMnemonic.READ
        assert s.operand == "NUM"
        assert s.is_valid is True

    def test_read_class_is_is(self):
        assert stmt("READ NUM").statement_class == IntermediateClass.IS

    def test_read_missing_operand(self):
        s = stmt("READ")
        assert s.is_valid is False

    def test_read_literal_is_invalid(self):
        s = stmt("READ ='5'")
        assert s.is_valid is False

    def test_read_constant_is_invalid(self):
        s = stmt("READ 5")
        assert s.is_valid is False


# ===========================================================================
# 15. PRINT
# ===========================================================================


class TestPrint:
    def test_print_symbol(self):
        s = stmt("PRINT RESULT")
        assert s.imperative == ImperativeMnemonic.PRINT
        assert s.operand == "RESULT"
        assert s.is_valid is True

    def test_print_class_is_is(self):
        assert stmt("PRINT RESULT").statement_class == IntermediateClass.IS

    def test_print_missing_operand(self):
        s = stmt("PRINT")
        assert s.is_valid is False


# ===========================================================================
# 16. STOP
# ===========================================================================


class TestStop:
    def test_stop_is_valid(self):
        s = stmt("STOP")
        assert s.imperative == ImperativeMnemonic.STOP
        assert s.is_valid is True

    def test_stop_no_operands(self):
        s = stmt("STOP")
        assert s.operand is None
        assert s.register is None

    def test_stop_class_is_is(self):
        assert stmt("STOP").statement_class == IntermediateClass.IS

    def test_stop_with_trailing_is_invalid(self):
        s = stmt("STOP EXTRA")
        assert s.is_valid is False


# ===========================================================================
# 17. DC
# ===========================================================================


class TestDc:
    def test_dc_constant(self):
        s = stmt("DC 5")
        assert s.declarative == DeclarativeMnemonic.DC
        assert s.operand == "5"
        assert s.is_valid is True

    def test_dc_class_is_dl(self):
        assert stmt("DC 5").statement_class == IntermediateClass.DL

    def test_dc_missing_operand(self):
        s = stmt("DC")
        assert s.is_valid is False

    def test_dc_symbol_operand_is_invalid(self):
        # DC requires a numeric constant
        s = stmt("DC LOOP")
        assert s.is_valid is False

    def test_dc_literal_is_invalid(self):
        s = stmt("DC ='5'")
        assert s.is_valid is False


# ===========================================================================
# 18. DS
# ===========================================================================


class TestDs:
    def test_ds_constant(self):
        s = stmt("DS 1")
        assert s.declarative == DeclarativeMnemonic.DS
        assert s.operand == "1"
        assert s.is_valid is True

    def test_ds_class_is_dl(self):
        assert stmt("DS 1").statement_class == IntermediateClass.DL

    def test_ds_missing_operand(self):
        s = stmt("DS")
        assert s.is_valid is False

    def test_ds_symbol_operand_is_invalid(self):
        s = stmt("DS LOOP")
        assert s.is_valid is False


# ===========================================================================
# 19. Label + instruction
# ===========================================================================


class TestLabelHandling:
    def test_label_before_sub(self):
        s = stmt("LOOP SUB AREG ='2'")
        assert s.label == "LOOP"
        assert s.imperative == ImperativeMnemonic.SUB

    def test_label_before_ds(self):
        s = stmt("RESULT DS 1")
        assert s.label == "RESULT"
        assert s.declarative == DeclarativeMnemonic.DS

    def test_label_before_mover(self):
        s = stmt("MYSTART MOVER AREG ='5'")
        assert s.label == "MYSTART"
        assert s.imperative == ImperativeMnemonic.MOVER

    def test_label_before_start(self):
        s = stmt("PROG START 100")
        assert s.label == "PROG"
        assert s.directive == Directive.START

    def test_label_not_confused_with_operand(self):
        # MOVER AREG RESULT — RESULT is the operand, not a label
        s = stmt("MOVER AREG RESULT")
        assert s.label is None
        assert s.operand == "RESULT"

    def test_symbol_without_following_mnemonic_is_error(self):
        # A bare SYMBOL with no mnemonic following it is invalid
        s = stmt("LOOP")
        assert s.is_valid is False

    def test_label_preserved_in_output(self):
        s = stmt("NEXT ADD AREG BREG")
        assert s.label == "NEXT"


# ===========================================================================
# 20. Instruction without label
# ===========================================================================


class TestNoLabel:
    def test_mover_no_label(self):
        s = stmt("MOVER AREG ='5'")
        assert s.label is None

    def test_start_no_label(self):
        assert stmt("START 100").label is None

    def test_stop_no_label(self):
        assert stmt("STOP").label is None


# ===========================================================================
# 21–24. Operand type identification
# ===========================================================================


class TestOperandTypes:
    def test_register_operand(self):
        # First register captured as .register
        s = stmt("ADD AREG BREG")
        assert s.register == Register.AREG

    def test_all_registers_identified(self):
        for reg in ["AREG", "BREG", "CREG", "DREG"]:
            s = stmt(f"MOVER {reg} RESULT")
            assert s.register == Register(reg)

    def test_literal_operand(self):
        s = stmt("MOVER AREG ='5'")
        assert s.operand == "='5'"

    def test_symbol_operand(self):
        s = stmt("MOVER AREG RESULT")
        assert s.operand == "RESULT"

    def test_constant_operand(self):
        s = stmt("MOVER AREG 100")
        assert s.operand == "100"

    def test_condition_code_operand(self):
        s = stmt("BC GT NEXT")
        assert s.condition_code == ConditionCode.GT


# ===========================================================================
# 25. Condition code operand
# ===========================================================================


class TestConditionCodeOperand:
    def test_lt(self):
        assert stmt("BC LT LOOP").condition_code == ConditionCode.LT

    def test_le(self):
        assert stmt("BC LE LOOP").condition_code == ConditionCode.LE

    def test_eq(self):
        assert stmt("BC EQ LOOP").condition_code == ConditionCode.EQ

    def test_gt(self):
        assert stmt("BC GT LOOP").condition_code == ConditionCode.GT

    def test_ge(self):
        assert stmt("BC GE LOOP").condition_code == ConditionCode.GE

    def test_any(self):
        assert stmt("BC ANY LOOP").condition_code == ConditionCode.ANY


# ===========================================================================
# 26. Wrong operand count (too many)
# ===========================================================================


class TestTooManyOperands:
    def test_stop_extra_operand(self):
        assert stmt("STOP EXTRA").is_valid is False

    def test_end_extra_operand(self):
        assert stmt("END EXTRA").is_valid is False

    def test_ltorg_extra_operand(self):
        assert stmt("LTORG EXTRA").is_valid is False

    def test_read_extra_operand(self):
        # READ takes one symbol; two operands is wrong
        s = stmt("READ NUM EXTRA")
        assert s.is_valid is False


# ===========================================================================
# 27. Missing operand
# ===========================================================================


class TestMissingOperand:
    def test_start_no_operand(self):
        assert stmt("START").is_valid is False

    def test_mover_no_second_operand(self):
        assert stmt("MOVER AREG").is_valid is False

    def test_mover_no_operands(self):
        assert stmt("MOVER").is_valid is False

    def test_bc_no_operands(self):
        assert stmt("BC").is_valid is False

    def test_ds_no_operand(self):
        assert stmt("DS").is_valid is False

    def test_read_no_operand(self):
        assert stmt("READ").is_valid is False


# ===========================================================================
# 28. Invalid operand type
# ===========================================================================


class TestInvalidOperandType:
    def test_mover_register_as_second_operand_is_invalid(self):
        s = stmt("MOVER AREG BREG")
        assert s.is_valid is False

    def test_read_receives_literal_is_invalid(self):
        s = stmt("READ ='5'")
        assert s.is_valid is False

    def test_dc_receives_symbol_is_invalid(self):
        s = stmt("DC LOOP")
        assert s.is_valid is False

    def test_start_receives_symbol_is_invalid(self):
        s = stmt("START LOOP")
        assert s.is_valid is False

    def test_movem_receives_literal_is_invalid(self):
        s = stmt("MOVEM AREG ='5'")
        assert s.is_valid is False


# ===========================================================================
# 29. Invalid register
# ===========================================================================


class TestInvalidRegister:
    def test_xreg_is_not_valid_register(self):
        # XREG is a SYMBOL, not a REGISTER
        s = stmt("MOVER XREG RESULT")
        assert s.is_valid is False

    def test_reg_is_not_valid_register(self):
        s = stmt("ADD REG BREG")
        assert s.is_valid is False


# ===========================================================================
# 30. Invalid condition code
# ===========================================================================


class TestInvalidConditionCode:
    def test_ne_not_valid(self):
        s = stmt("BC NE LOOP")
        assert s.is_valid is False

    def test_symbol_as_condition_code_is_invalid(self):
        # LOOP is a SYMBOL, not a CONDITION_CODE
        s = stmt("BC LOOP NEXT")
        assert s.is_valid is False

    def test_number_as_condition_code_is_invalid(self):
        s = stmt("BC 1 NEXT")
        assert s.is_valid is False


# ===========================================================================
# 31. Comment tokens ignored by grammar
# ===========================================================================


class TestCommentHandling:
    def test_comment_after_instruction_ignored(self):
        s = stmt("STOP ; halt the machine")
        assert s.imperative == ImperativeMnemonic.STOP
        assert s.is_valid is True

    def test_comment_after_mover_ignored(self):
        s = stmt("MOVER AREG ='5' ; load five")
        assert s.is_valid is True
        assert s.operand == "='5'"

    def test_inline_comment_does_not_become_operand(self):
        s = stmt("ADD AREG BREG ; add registers")
        assert s.operand == "BREG"
        assert s.is_valid is True

    def test_comment_only_line_produces_no_statement(self):
        result = parse("; just a comment")
        assert result.statement_count == 0


# ===========================================================================
# 32. Empty lines
# ===========================================================================


class TestEmptyLines:
    def test_empty_source_gives_no_statements(self):
        result = parse("")
        assert result.statement_count == 0
        assert result.success is True

    def test_blank_line_between_statements_ignored(self):
        result = parse("START 100\n\nEND")
        assert result.statement_count == 2

    def test_multiple_blank_lines_ignored(self):
        result = parse("\n\n\nSTART 100\n\n\nEND\n\n")
        assert result.statement_count == 2

    def test_whitespace_only_input_gives_no_statements(self):
        result = parse("   \t  ")
        assert result.statement_count == 0


# ===========================================================================
# 33. Multiple statements
# ===========================================================================


class TestMultipleStatements:
    def test_three_statements(self):
        result = parse("START 100\nSTOP\nEND")
        assert result.statement_count == 3

    def test_statement_order_preserved(self):
        result = parse("START 100\nMOVER AREG ='5'\nEND")
        assert result.statements[0].directive == Directive.START
        assert result.statements[1].imperative == ImperativeMnemonic.MOVER
        assert result.statements[2].directive == Directive.END

    def test_line_numbers_match_source(self):
        result = parse("START 100\nMOVER AREG ='5'\nEND")
        assert result.statements[0].line_number == 1
        assert result.statements[1].line_number == 2
        assert result.statements[2].line_number == 3


# ===========================================================================
# 34. Error recovery
# ===========================================================================


class TestErrorRecovery:
    def test_bad_line_does_not_prevent_next_line_parsing(self):
        # Line 2 is bad, line 3 should still parse
        result = parse("START 100\nMOVER AREG\nEND")
        assert result.statement_count == 3
        # line 1 (START) valid, line 2 (MOVER) invalid, line 3 (END) valid
        assert result.statements[0].is_valid is True
        assert result.statements[1].is_valid is False
        assert result.statements[2].is_valid is True

    def test_success_false_when_any_error(self):
        result = parse("START 100\nMOVER AREG\nEND")
        assert result.success is False

    def test_success_true_when_all_valid(self):
        result = parse("START 100\nSTOP\nEND")
        assert result.success is True

    def test_multiple_errors_all_reported(self):
        result = parse("START\nMOVER\nDS")
        assert len(result.diagnostics) >= 3

    def test_valid_statements_after_multiple_errors(self):
        result = parse("START\nMOVER\nSTOP\nEND")
        # STOP and END should be valid despite earlier errors
        stop_stmt = next(s for s in result.statements if s.imperative == ImperativeMnemonic.STOP)
        assert stop_stmt.is_valid is True


# ===========================================================================
# 35. Exact error location
# ===========================================================================


class TestErrorLocation:
    def test_error_has_line_number(self):
        result = parse("START 100\nMOVER AREG\nEND")
        bad = result.statements[1]
        assert bad.errors[0].line is not None
        assert bad.errors[0].line == 2

    def test_error_has_column(self):
        result = parse("MOVER AREG")
        bad = result.statements[0]
        assert bad.errors[0].column is not None
        assert bad.errors[0].column >= 1

    def test_error_message_is_not_empty(self):
        result = parse("START")
        assert len(result.statements[0].errors[0].message) > 0

    def test_error_has_expected_field(self):
        result = parse("START")
        err = result.statements[0].errors[0]
        assert err.expected is not None


# ===========================================================================
# 36. Undefined symbol is NOT a syntax error
# ===========================================================================


class TestUndefinedSymbolNotSyntaxError:
    def test_mover_with_undefined_symbol_is_valid(self):
        # UNKNOWN_VAR is not declared anywhere — but that's Pass-I's problem
        s = stmt("MOVER AREG UNKNOWN_VAR")
        assert s.is_valid is True
        assert s.operand == "UNKNOWN_VAR"

    def test_bc_with_unknown_target_is_valid(self):
        s = stmt("BC LT NONEXISTENT_LABEL")
        assert s.is_valid is True

    def test_movem_with_unknown_symbol_is_valid(self):
        s = stmt("MOVEM AREG NOWHERE")
        assert s.is_valid is True


# ===========================================================================
# 37. Duplicate symbol is NOT a parser error
# ===========================================================================


class TestDuplicateSymbolNotParserError:
    def test_same_label_on_two_lines_does_not_error(self):
        result = parse("LOOP ADD AREG BREG\nLOOP SUB AREG BREG")
        # Both lines should parse successfully at the syntax level
        assert result.statements[0].is_valid is True
        assert result.statements[1].is_valid is True

    def test_success_true_for_duplicate_labels(self):
        result = parse("LOOP ADD AREG BREG\nLOOP SUB AREG BREG")
        assert result.success is True


# ===========================================================================
# 38. Canonical demo program — full verification
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
    def setup_method(self):
        self.result = parse(CANONICAL)
        self.stmts = self.result.statements

    def test_success(self):
        assert self.result.success is True

    def test_no_diagnostics(self):
        assert self.result.diagnostics == []

    def test_statement_count(self):
        assert self.result.statement_count == 7

    # --- Statement 1: START 100 ---
    def test_s1_directive(self):
        assert self.stmts[0].directive == Directive.START

    def test_s1_operand(self):
        assert self.stmts[0].operand == "100"

    def test_s1_no_label(self):
        assert self.stmts[0].label is None

    def test_s1_class(self):
        assert self.stmts[0].statement_class == IntermediateClass.AD

    def test_s1_line(self):
        assert self.stmts[0].line_number == 1

    # --- Statement 2: MOVER AREG ='5' ---
    def test_s2_imperative(self):
        assert self.stmts[1].imperative == ImperativeMnemonic.MOVER

    def test_s2_register(self):
        assert self.stmts[1].register == Register.AREG

    def test_s2_operand(self):
        assert self.stmts[1].operand == "='5'"

    def test_s2_no_label(self):
        assert self.stmts[1].label is None

    def test_s2_class(self):
        assert self.stmts[1].statement_class == IntermediateClass.IS

    # --- Statement 3: ADD BREG ='1' ---
    def test_s3_imperative(self):
        assert self.stmts[2].imperative == ImperativeMnemonic.ADD

    def test_s3_register(self):
        assert self.stmts[2].register == Register.BREG

    def test_s3_operand(self):
        assert self.stmts[2].operand == "='1'"

    def test_s3_no_label(self):
        assert self.stmts[2].label is None

    # --- Statement 4: LOOP SUB AREG ='2' ---
    def test_s4_label(self):
        assert self.stmts[3].label == "LOOP"

    def test_s4_imperative(self):
        assert self.stmts[3].imperative == ImperativeMnemonic.SUB

    def test_s4_register(self):
        assert self.stmts[3].register == Register.AREG

    def test_s4_operand(self):
        assert self.stmts[3].operand == "='2'"

    def test_s4_line(self):
        assert self.stmts[3].line_number == 4

    # --- Statement 5: MOVEM AREG RESULT ---
    def test_s5_imperative(self):
        assert self.stmts[4].imperative == ImperativeMnemonic.MOVEM

    def test_s5_register(self):
        assert self.stmts[4].register == Register.AREG

    def test_s5_operand(self):
        assert self.stmts[4].operand == "RESULT"

    def test_s5_no_label(self):
        assert self.stmts[4].label is None

    # --- Statement 6: RESULT DS 1 ---
    def test_s6_label(self):
        assert self.stmts[5].label == "RESULT"

    def test_s6_declarative(self):
        assert self.stmts[5].declarative == DeclarativeMnemonic.DS

    def test_s6_operand(self):
        assert self.stmts[5].operand == "1"

    def test_s6_class(self):
        assert self.stmts[5].statement_class == IntermediateClass.DL

    def test_s6_line(self):
        assert self.stmts[5].line_number == 6

    # --- Statement 7: END ---
    def test_s7_directive(self):
        assert self.stmts[6].directive == Directive.END

    def test_s7_no_operand(self):
        assert self.stmts[6].operand is None

    def test_s7_no_label(self):
        assert self.stmts[6].label is None

    def test_s7_line(self):
        assert self.stmts[6].line_number == 7

    def test_all_statements_valid(self):
        for i, s in enumerate(self.stmts):
            assert s.is_valid is True, (
                f"Statement {i + 1} should be valid: {s.errors}"
            )


# ===========================================================================
# SyntaxResult fields
# ===========================================================================


class TestSyntaxResultFields:
    def test_statement_count_matches_list_length(self):
        result = parse(CANONICAL)
        assert result.statement_count == len(result.statements)

    def test_diagnostics_is_list(self):
        assert isinstance(parse(CANONICAL).diagnostics, list)

    def test_success_is_bool(self):
        assert isinstance(parse(CANONICAL).success, bool)

    def test_empty_source_success_true(self):
        assert parse("").success is True

    def test_invalid_source_success_false(self):
        assert parse("START").success is False


# ===========================================================================
# Case insensitivity
# ===========================================================================


class TestCaseInsensitivity:
    def test_lowercase_mover(self):
        s = stmt("mover areg ='5'")
        assert s.imperative == ImperativeMnemonic.MOVER
        assert s.register == Register.AREG
        assert s.is_valid is True

    def test_lowercase_start(self):
        s = stmt("start 100")
        assert s.directive == Directive.START
        assert s.is_valid is True

    def test_mixedcase_ds(self):
        s = stmt("RESULT ds 1")
        assert s.declarative == DeclarativeMnemonic.DS
        assert s.label == "RESULT"

    def test_lowercase_bc_with_cc(self):
        s = stmt("bc lt loop")
        assert s.imperative == ImperativeMnemonic.BC
        assert s.condition_code == ConditionCode.LT
        assert s.is_valid is True
