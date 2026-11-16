"""
Unit tests — Language enumeration tables.

Verifies that every keyword defined in ``engine.common.enums`` is correct,
complete, and consistent with the SysForge educational assembly language
specification.
"""

from __future__ import annotations

import pytest

from engine.common.enums import (
    ALL_KEYWORDS,
    CONDITION_CODE_NUMBER,
    DECLARATIVE_KEYWORDS,
    DIRECTIVE_KEYWORDS,
    IMPERATIVE_KEYWORDS,
    OPCODE_TABLE,
    OPCODE_TO_MNEMONIC,
    REGISTER_KEYWORDS,
    REGISTER_NUMBER,
    AnalysisStage,
    ConditionCode,
    DeclarativeMnemonic,
    Directive,
    ImperativeMnemonic,
    IntermediateClass,
    OperandType,
    Register,
    StageStatus,
    TokenType,
)


class TestDirectives:
    def test_all_five_directives_exist(self):
        names = {d.value for d in Directive}
        assert names == {"START", "END", "ORIGIN", "EQU", "LTORG"}

    def test_directive_keywords_frozenset_matches(self):
        assert DIRECTIVE_KEYWORDS == {d.value for d in Directive}


class TestImperativeMnemonics:
    EXPECTED = {
        "ADD", "SUB", "MULT", "MOVER", "MOVEM",
        "COMP", "BC", "DIV", "READ", "PRINT", "STOP",
    }

    def test_all_eleven_imperatives_exist(self):
        assert {m.value for m in ImperativeMnemonic} == self.EXPECTED

    def test_imperative_keywords_frozenset_matches(self):
        assert IMPERATIVE_KEYWORDS == self.EXPECTED


class TestDeclarativeMnemonics:
    def test_dc_and_ds_exist(self):
        assert {m.value for m in DeclarativeMnemonic} == {"DC", "DS"}

    def test_declarative_keywords_frozenset_matches(self):
        assert DECLARATIVE_KEYWORDS == {"DC", "DS"}


class TestRegisters:
    def test_four_registers_exist(self):
        assert {r.value for r in Register} == {"AREG", "BREG", "CREG", "DREG"}

    def test_register_numbers_are_1_through_4(self):
        assert REGISTER_NUMBER[Register.AREG] == 1
        assert REGISTER_NUMBER[Register.BREG] == 2
        assert REGISTER_NUMBER[Register.CREG] == 3
        assert REGISTER_NUMBER[Register.DREG] == 4

    def test_register_keywords_frozenset_matches(self):
        assert REGISTER_KEYWORDS == {"AREG", "BREG", "CREG", "DREG"}


class TestConditionCodes:
    def test_six_condition_codes_exist(self):
        assert {c.value for c in ConditionCode} == {"LT", "LE", "EQ", "GT", "GE", "ANY"}

    def test_condition_code_numbers(self):
        assert CONDITION_CODE_NUMBER[ConditionCode.LT] == 1
        assert CONDITION_CODE_NUMBER[ConditionCode.LE] == 2
        assert CONDITION_CODE_NUMBER[ConditionCode.EQ] == 3
        assert CONDITION_CODE_NUMBER[ConditionCode.GT] == 4
        assert CONDITION_CODE_NUMBER[ConditionCode.GE] == 5
        assert CONDITION_CODE_NUMBER[ConditionCode.ANY] == 6


class TestOpcodeTables:
    def test_stop_has_opcode_1(self):
        assert OPCODE_TABLE[ImperativeMnemonic.STOP] == 1

    def test_mover_has_opcode_5(self):
        assert OPCODE_TABLE[ImperativeMnemonic.MOVER] == 5

    def test_all_imperatives_have_opcode(self):
        for mnemonic in ImperativeMnemonic:
            assert mnemonic in OPCODE_TABLE

    def test_reverse_lookup_is_consistent(self):
        for mnemonic, code in OPCODE_TABLE.items():
            assert OPCODE_TO_MNEMONIC[code] == mnemonic

    def test_opcodes_are_unique(self):
        codes = list(OPCODE_TABLE.values())
        assert len(codes) == len(set(codes))


class TestKeywordSets:
    def test_all_keywords_is_union(self):
        expected = (
            DIRECTIVE_KEYWORDS
            | IMPERATIVE_KEYWORDS
            | DECLARATIVE_KEYWORDS
            | REGISTER_KEYWORDS
            | {c.value for c in ConditionCode}
        )
        assert ALL_KEYWORDS == expected

    def test_no_overlap_between_directives_and_imperatives(self):
        assert DIRECTIVE_KEYWORDS.isdisjoint(IMPERATIVE_KEYWORDS)

    def test_no_overlap_between_imperatives_and_registers(self):
        assert IMPERATIVE_KEYWORDS.isdisjoint(REGISTER_KEYWORDS)

    def test_sample_keywords_are_in_all_keywords(self):
        for kw in ["START", "END", "MOVER", "ADD", "DC", "DS", "AREG", "LT"]:
            assert kw in ALL_KEYWORDS


class TestAnalysisStage:
    def test_lexical_stage_value(self):
        assert AnalysisStage.LEXICAL == "lexical"

    def test_pass_one_stage_value(self):
        assert AnalysisStage.PASS_ONE == "pass-one"

    def test_all_stages_are_strings(self):
        for stage in AnalysisStage:
            assert isinstance(stage.value, str)


class TestStageStatus:
    def test_five_statuses_exist(self):
        values = {s.value for s in StageStatus}
        assert "NOT_STARTED" in values
        assert "COMPLETED" in values
        assert "ERROR" in values
        assert "NOT_IMPLEMENTED" in values
        assert "IN_PROGRESS" in values


class TestIntermediateClass:
    def test_is_dl_ad_exist(self):
        assert {c.value for c in IntermediateClass} == {"IS", "DL", "AD"}


class TestTokenType:
    def test_key_token_types_exist(self):
        values = {t.value for t in TokenType}
        for expected in ["DIRECTIVE", "IMPERATIVE", "REGISTER", "LITERAL", "SYMBOL", "NUMBER"]:
            assert expected in values
