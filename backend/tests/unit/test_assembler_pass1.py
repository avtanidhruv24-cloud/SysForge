"""
Unit tests — Assembler Pass-I engine (Phase 5).

Tests the deterministic educational Pass-I implementation against the full
spectrum of assembler requirements:
  - Test A: Canonical basic program
  - Test B: DC and DS declarative statements
  - Test C: Forward reference resolution
  - Test D: EQU + ORIGIN directives
  - Test E: LTORG literal allocation
  - Test F: Multiple literal pools
  - Test G: Duplicate literal handling in pool
  - Test H: Duplicate symbol error diagnostic
  - Test I: Undefined symbol error diagnostic
  - Test J: Multi-error recovery
  - Additional edge cases (missing START, missing END, expressions, STOP, BC)
"""

from __future__ import annotations

import pytest

from engine.assembler import AssemblerPass1
from engine.lexer import Lexer
from engine.parser import Parser
from engine.common.enums import IntermediateClass, OperandType


@pytest.fixture
def assemble():
    """Helper fixture: compiles source through Lexer -> Parser -> AssemblerPass1."""
    lexer = Lexer()
    parser = Parser()
    pass1 = AssemblerPass1()

    def _assemble(source: str):
        lex_res = lexer.analyze(source)
        syn_res = parser.parse(lex_res)
        return pass1.assemble(syn_res)

    return _assemble


# ===========================================================================
# TEST A — Canonical Basic Program
# ===========================================================================


class TestCanonicalProgram:
    SOURCE = (
        "START 100\n"
        "MOVER AREG ='5'\n"
        "ADD BREG ='1'\n"
        "LOOP SUB AREG ='2'\n"
        "MOVEM AREG RESULT\n"
        "RESULT DS 1\n"
        "END"
    )

    def test_success_true(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        assert len([d for d in res.diagnostics if d.get("severity") == "ERROR"]) == 0

    def test_starting_address(self, assemble):
        res = assemble(self.SOURCE)
        assert res.starting_address == 100

    def test_final_location_counter(self, assemble):
        res = assemble(self.SOURCE)
        # 100 (START) -> MOVER (100->101) -> ADD (101->102) -> LOOP SUB (102->103)
        # -> MOVEM (103->104) -> RESULT DS 1 (104->105)
        # At END: 3 literals allocated: ='5' (105), ='1' (106), ='2' (107)
        # Final LC = 108
        assert res.final_location_counter == 108

    def test_symbol_table(self, assemble):
        res = assemble(self.SOURCE)
        sym_map = {s.name: s for s in res.symbol_table}
        assert "LOOP" in sym_map
        assert sym_map["LOOP"].value == 102
        assert sym_map["LOOP"].defined_at_line == 4
        assert sym_map["LOOP"].is_defined is True

        assert "RESULT" in sym_map
        assert sym_map["RESULT"].value == 104
        assert sym_map["RESULT"].defined_at_line == 6
        assert sym_map["RESULT"].is_defined is True
        assert 5 in sym_map["RESULT"].references

    def test_literal_table(self, assemble):
        res = assemble(self.SOURCE)
        assert len(res.literal_table) == 3
        lit_map = {l.value: l for l in res.literal_table}
        assert lit_map["='5'"].address == 105
        assert lit_map["='1'"].address == 106
        assert lit_map["='2'"].address == 107
        assert lit_map["='5'"].pool_index == 0

    def test_pool_table(self, assemble):
        res = assemble(self.SOURCE)
        assert len(res.pool_table) == 1
        pool0 = res.pool_table[0]
        assert pool0.pool_index == 0
        assert pool0.littab_start_index == 0
        assert pool0.literal_count == 3
        assert pool0.trigger == "END"

    def test_intermediate_code_emitted(self, assemble):
        res = assemble(self.SOURCE)
        assert len(res.intermediate_code) >= 7
        # Line 1: START
        assert res.intermediate_code[0].statement_class == IntermediateClass.AD
        assert res.intermediate_code[0].mnemonic == "START"
        # Line 2: MOVER AREG ='5'
        mover = res.intermediate_code[1]
        assert mover.statement_class == IntermediateClass.IS
        assert mover.mnemonic == "MOVER"
        assert mover.location_counter == 100
        assert any(op.type == OperandType.REGISTER and op.value == "1" for op in mover.operands)
        assert any(op.type == OperandType.LITERAL for op in mover.operands)

    def test_lc_trace_populated(self, assemble):
        res = assemble(self.SOURCE)
        assert len(res.lc_trace) >= 7
        for entry in res.lc_trace:
            assert entry.source_line >= 1
            assert len(entry.statement) > 0
            assert len(entry.action) > 0


# ===========================================================================
# TEST B — DC and DS
# ===========================================================================


class TestDeclarativesDcDs:
    SOURCE = (
        "START 200\n"
        "VALUE DC 10\n"
        "ARRAY DS 5\n"
        "END"
    )

    def test_dc_and_ds_addresses(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        sym_map = {s.name: s for s in res.symbol_table}
        assert sym_map["VALUE"].value == 200
        assert sym_map["ARRAY"].value == 201

    def test_lc_increments(self, assemble):
        res = assemble(self.SOURCE)
        # START 200 -> VALUE DC 10 (200->201) -> ARRAY DS 5 (201->206) -> END (206)
        assert res.final_location_counter == 206

    def test_dc_ds_intermediate_classes(self, assemble):
        res = assemble(self.SOURCE)
        dc_rec = [r for r in res.intermediate_code if r.mnemonic == "DC"][0]
        ds_rec = [r for r in res.intermediate_code if r.mnemonic == "DS"][0]
        assert dc_rec.statement_class == IntermediateClass.DL
        assert ds_rec.statement_class == IntermediateClass.DL
        assert dc_rec.operands[0].value == "10"
        assert ds_rec.operands[0].value == "5"


# ===========================================================================
# TEST C — Forward Reference Resolution
# ===========================================================================


class TestForwardReference:
    SOURCE = (
        "START 100\n"
        "MOVER AREG ='5'\n"
        "MOVEM AREG RESULT\n"
        "RESULT DS 1\n"
        "END"
    )

    def test_forward_reference_resolved(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        sym_map = {s.name: s for s in res.symbol_table}
        result_sym = sym_map["RESULT"]
        assert result_sym.is_defined is True
        assert result_sym.value == 102
        assert result_sym.forward_reference is True
        assert 3 in result_sym.references

    def test_no_undefined_symbol_diagnostic(self, assemble):
        res = assemble(self.SOURCE)
        errs = [d for d in res.diagnostics if d.get("severity") == "ERROR"]
        assert len(errs) == 0


# ===========================================================================
# TEST D — EQU and ORIGIN
# ===========================================================================


class TestEquAndOrigin:
    SOURCE = (
        "START 100\n"
        "VALUE EQU 200\n"
        "ORIGIN VALUE\n"
        "RESULT DS 1\n"
        "END"
    )

    def test_equ_symbol_value(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        sym_map = {s.name: s for s in res.symbol_table}
        assert sym_map["VALUE"].value == 200
        assert sym_map["VALUE"].is_defined is True

    def test_origin_relocates_lc(self, assemble):
        res = assemble(self.SOURCE)
        sym_map = {s.name: s for s in res.symbol_table}
        assert sym_map["RESULT"].value == 200
        # RESULT DS 1 at 200 -> final LC = 201
        assert res.final_location_counter == 201

    def test_equ_does_not_advance_lc(self, assemble):
        res = assemble(self.SOURCE)
        equ_trace = [t for t in res.lc_trace if "EQU" in t.statement][0]
        assert equ_trace.lc_before == equ_trace.lc_after == 100


# ===========================================================================
# TEST E — LTORG Literal Allocation
# ===========================================================================


class TestLtorgDirective:
    SOURCE = (
        "START 100\n"
        "MOVER AREG ='5'\n"
        "ADD AREG ='1'\n"
        "LTORG\n"
        "MOVER BREG ='10'\n"
        "END"
    )

    def test_ltorg_allocates_pending_literals(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        lit_map = {l.value: l for l in res.literal_table}
        # MOVER (100->101), ADD (101->102)
        # LTORG at 102 allocates ='5' at 102, ='1' at 103 -> LC becomes 104
        assert lit_map["='5'"].address == 102
        assert lit_map["='1'"].address == 103
        assert lit_map["='5'"].pool_index == 0
        assert lit_map["='1'"].pool_index == 0

        # MOVER BREG ='10' at 104 (104->105)
        # END allocates ='10' at 105 -> final LC = 106
        assert lit_map["='10'"].address == 105
        assert lit_map["='10'"].pool_index == 1
        assert res.final_location_counter == 106


# ===========================================================================
# TEST F — Multiple Literal Pools
# ===========================================================================


class TestMultiplePools:
    SOURCE = (
        "START 100\n"
        "MOVER AREG ='1'\n"
        "LTORG\n"
        "MOVER AREG ='2'\n"
        "LTORG\n"
        "MOVER AREG ='3'\n"
        "END"
    )

    def test_pool_boundaries_and_count(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        assert len(res.pool_table) == 3

        p0 = res.pool_table[0]
        assert p0.pool_index == 0
        assert p0.littab_start_index == 0
        assert p0.literal_count == 1
        assert p0.trigger == "LTORG"

        p1 = res.pool_table[1]
        assert p1.pool_index == 1
        assert p1.littab_start_index == 1
        assert p1.literal_count == 1
        assert p1.trigger == "LTORG"

        p2 = res.pool_table[2]
        assert p2.pool_index == 2
        assert p2.littab_start_index == 2
        assert p2.literal_count == 1
        assert p2.trigger == "END"


# ===========================================================================
# TEST G — Duplicate Literals in Same Pool
# ===========================================================================


class TestDuplicateLiterals:
    SOURCE = (
        "START 100\n"
        "MOVER AREG ='5'\n"
        "ADD BREG ='5'\n"
        "SUB CREG ='5'\n"
        "END"
    )

    def test_duplicate_literals_shared_in_pool(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is True
        # Only one literal entry for ='5' in this pool
        assert len(res.literal_table) == 1
        entry = res.literal_table[0]
        assert entry.value == "='5'"
        assert len(entry.references) == 3
        # Address allocated at END (100+3 = 103)
        assert entry.address == 103
        assert res.final_location_counter == 104


# ===========================================================================
# TEST H — Duplicate Symbol Diagnostic
# ===========================================================================


class TestDuplicateSymbol:
    SOURCE = (
        "START 100\n"
        "LOOP MOVER AREG ='1'\n"
        "LOOP ADD BREG ='2'\n"
        "END"
    )

    def test_duplicate_symbol_error(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is False
        errs = [d for d in res.diagnostics if d.get("code") == "DUPLICATE_SYMBOL"]
        assert len(errs) >= 1
        assert "LOOP" in errs[0]["message"]


# ===========================================================================
# TEST I — Undefined Symbol Diagnostic
# ===========================================================================


class TestUndefinedSymbol:
    SOURCE = (
        "START 100\n"
        "MOVER AREG MISSING\n"
        "END"
    )

    def test_undefined_symbol_detected_at_end(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is False
        errs = [d for d in res.diagnostics if d.get("code") == "UNDEFINED_SYMBOL"]
        assert len(errs) >= 1
        assert "MISSING" in errs[0]["message"]


# ===========================================================================
# TEST J — Multi-Error Recovery
# ===========================================================================


class TestErrorRecovery:
    SOURCE = (
        "START 100\n"
        "LABEL1 MOVER AREG MISSING1\n"
        "LABEL1 ADD BREG MISSING2\n"
        "VALID DS 2\n"
        "END"
    )

    def test_recovers_and_reports_all_errors(self, assemble):
        res = assemble(self.SOURCE)
        assert res.success is False
        codes = [d["code"] for d in res.diagnostics if d.get("severity") == "ERROR"]
        assert "DUPLICATE_SYMBOL" in codes
        assert "UNDEFINED_SYMBOL" in codes
        # Processing still continued to VALID symbol
        sym_map = {s.name: s for s in res.symbol_table}
        assert "VALID" in sym_map
        assert sym_map["VALID"].is_defined is True


# ===========================================================================
# Additional Edge Cases
# ===========================================================================


class TestEdgeCases:
    def test_stop_instruction(self, assemble):
        source = "START 100\nSTOP\nEND"
        res = assemble(source)
        assert res.success is True
        assert res.final_location_counter == 101
        rec = [r for r in res.intermediate_code if r.mnemonic == "STOP"][0]
        assert rec.statement_class == IntermediateClass.IS

    def test_bc_instruction(self, assemble):
        source = "START 100\nLOOP MOVER AREG ='1'\nBC LT LOOP\nEND"
        res = assemble(source)
        assert res.success is True
        bc_rec = [r for r in res.intermediate_code if r.mnemonic == "BC"][0]
        assert bc_rec.statement_class == IntermediateClass.IS
        # Operand 1 should be condition code
        assert any(op.type == OperandType.CONDITION for op in bc_rec.operands)
        # Operand 2 should be symbol reference
        assert any(op.type == OperandType.SYMBOL for op in bc_rec.operands)

    def test_missing_start_defaults_lc(self, assemble):
        source = "MOVER AREG ='1'\nEND"
        res = assemble(source)
        # Should default LC to 0 with a warning
        assert res.starting_address == 0
        assert res.final_location_counter == 2  # MOVER at 0 -> 1, lit at 1 -> 2

    def test_invalid_start_address(self, assemble):
        source = "START -50\nEND"
        res = assemble(source)
        errs = [d for d in res.diagnostics if d.get("code") == "INVALID_START"]
        assert len(errs) >= 1


# ===========================================================================
# Phase 5.1 — No Trailing Empty POOLTAB Regression Tests
# ===========================================================================


class TestTrailingEmptyPool:
    def test_multiple_ltorg_without_trailing_literals(self, assemble):
        """
        Pool #1 -> 2 literals -> LTORG
        Pool #2 -> 2 literals -> LTORG
        END (0 literals after 2nd LTORG)
        Should emit exactly 2 pools, NOT an empty Pool #3.
        """
        source = (
            "START 100\n"
            "MOVER AREG ='1'\n"
            "ADD BREG ='2'\n"
            "LTORG\n"
            "MOVER AREG ='3'\n"
            "ADD BREG ='4'\n"
            "LTORG\n"
            "END"
        )
        res = assemble(source)
        assert res.success is True
        assert len(res.pool_table) == 2

        p0 = res.pool_table[0]
        assert p0.pool_number == 1
        assert p0.literal_count == 2
        assert p0.trigger == "LTORG"

        p1 = res.pool_table[1]
        assert p1.pool_number == 2
        assert p1.literal_count == 2
        assert p1.trigger == "LTORG"

        # Verify literal count and allocation unchanged
        assert len(res.literal_table) == 4
        assert res.literal_table[0].address == 102
        assert res.literal_table[1].address == 103
        assert res.literal_table[2].address == 106
        assert res.literal_table[3].address == 107

    def test_program_with_zero_literals_has_no_empty_pool(self, assemble):
        source = "START 100\nSTOP\nEND"
        res = assemble(source)
        assert res.success is True
        assert len(res.literal_table) == 0
        assert len(res.pool_table) == 0

    def test_consecutive_ltorg_no_empty_pool(self, assemble):
        source = (
            "START 100\n"
            "MOVER AREG ='10'\n"
            "LTORG\n"
            "LTORG\n"
            "MOVER AREG ='20'\n"
            "END"
        )
        res = assemble(source)
        assert res.success is True
        assert len(res.pool_table) == 2
        assert res.pool_table[0].pool_number == 1
        assert res.pool_table[0].literal_count == 1
        assert res.pool_table[1].pool_number == 2
        assert res.pool_table[1].literal_count == 1

