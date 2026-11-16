"""
Unit tests — Pydantic domain model validation.

Verifies that domain models accept valid data, reject invalid data, and
serialise to the shapes the frontend expects.

These tests use only the model constructors — no engine or API calls.
"""

from __future__ import annotations

import pytest

from engine.common.enums import (
    AnalysisStage,
    ConditionCode,
    IntermediateClass,
    OperandType,
    Register,
    StageStatus,
    TokenType,
)


# ---------------------------------------------------------------------------
# Token models
# ---------------------------------------------------------------------------


class TestSourceSpan:
    def test_valid_span(self):
        from app.models.tokens import SourceSpan
        s = SourceSpan(line=1, column=1, length=5)
        assert s.line == 1 and s.length == 5

    def test_rejects_zero_line(self):
        from app.models.tokens import SourceSpan
        with pytest.raises(Exception):
            SourceSpan(line=0, column=1, length=1)


class TestToken:
    def test_valid_token(self):
        from app.models.tokens import Token
        t = Token(type=TokenType.IMPERATIVE, value="MOVER", line=2, column=1)
        assert t.value == "MOVER"
        assert t.type == TokenType.IMPERATIVE

    def test_token_serialisation(self):
        from app.models.tokens import Token
        t = Token(type=TokenType.REGISTER, value="AREG", line=1, column=8)
        d = t.model_dump()
        assert d["type"] == "REGISTER"
        assert d["value"] == "AREG"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TestAnalysisRequest:
    def test_accepts_canonical_source(self, canonical_source):
        from app.models.requests import AnalysisRequest
        req = AnalysisRequest(source_code=canonical_source)
        assert req.source_code.startswith("START")

    def test_strips_leading_trailing_whitespace(self):
        from app.models.requests import AnalysisRequest
        req = AnalysisRequest(source_code="  START 100\nEND  ")
        assert not req.source_code.startswith(" ")

    def test_rejects_empty_source(self):
        from app.models.requests import AnalysisRequest
        with pytest.raises(Exception):
            AnalysisRequest(source_code="")

    def test_rejects_whitespace_only_source(self):
        from app.models.requests import AnalysisRequest
        with pytest.raises(Exception):
            AnalysisRequest(source_code="   \n\t  ")

    def test_stages_defaults_to_none(self, canonical_source):
        from app.models.requests import AnalysisRequest
        req = AnalysisRequest(source_code=canonical_source)
        assert req.stages is None

    def test_explicit_stages_accepted(self, canonical_source):
        from app.models.requests import AnalysisRequest
        req = AnalysisRequest(
            source_code=canonical_source,
            stages=[AnalysisStage.LEXICAL, AnalysisStage.SYNTAX],
        )
        assert len(req.stages) == 2


# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------


class TestAnalysisSession:
    def test_session_id_is_generated(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        assert len(s.session_id) > 0

    def test_two_sessions_have_different_ids(self):
        from app.models.sessions import AnalysisSession
        s1 = AnalysisSession(source_code="START 100\nEND")
        s2 = AnalysisSession(source_code="START 100\nEND")
        assert s1.session_id != s2.session_id

    def test_all_stages_start_as_not_started(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        for entry in s.stage_statuses.values():
            assert entry.status == StageStatus.NOT_STARTED

    def test_completed_stages_initially_empty(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        assert s.completed_stages == []

    def test_symbol_table_empty_before_pass1(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        assert s.symbol_table == []

    def test_set_in_progress_updates_status(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        s.set_in_progress(AnalysisStage.LEXICAL)
        assert s.get_status(AnalysisStage.LEXICAL).status == StageStatus.IN_PROGRESS

    def test_set_completed_updates_status(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        s.set_completed(AnalysisStage.LEXICAL)
        assert s.get_status(AnalysisStage.LEXICAL).status == StageStatus.COMPLETED
        assert AnalysisStage.LEXICAL in s.completed_stages

    def test_set_not_implemented_updates_status(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        s.set_not_implemented(AnalysisStage.LEXICAL)
        assert s.get_status(AnalysisStage.LEXICAL).status == StageStatus.NOT_IMPLEMENTED

    def test_has_errors_false_initially(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        assert s.has_errors is False

    def test_has_errors_true_after_error(self):
        from app.models.sessions import AnalysisSession
        s = AnalysisSession(source_code="START 100\nEND")
        s.set_error(AnalysisStage.LEXICAL, error_count=1)
        assert s.has_errors is True


# ---------------------------------------------------------------------------
# Assembler models
# ---------------------------------------------------------------------------


class TestSymbolTableEntry:
    def test_basic_entry(self):
        from app.models.assembler import SymbolTableEntry
        entry = SymbolTableEntry(name="LOOP", value=102, defined_at_line=4)
        assert entry.name == "LOOP"
        assert entry.value == 102

    def test_defaults(self):
        from app.models.assembler import SymbolTableEntry
        entry = SymbolTableEntry(name="RESULT", value=104)
        assert entry.is_defined is True
        assert entry.references == []


class TestLiteralTableEntry:
    def test_literal_entry(self):
        from app.models.assembler import LiteralTableEntry
        entry = LiteralTableEntry(value="='5'", pool_index=0)
        assert entry.value == "='5'"
        assert entry.pool_index == 0
        assert entry.address is None   # not assigned until LTORG


class TestPoolTableEntry:
    def test_pool_entry(self):
        from app.models.assembler import PoolTableEntry
        entry = PoolTableEntry(pool_index=0, littab_start_index=0, literal_count=3)
        assert entry.literal_count == 3


class TestIntermediateRecord:
    def test_record_creation(self):
        from app.models.assembler import IntermediateRecord
        rec = IntermediateRecord(
            source_line=2,
            location_counter=100,
            statement_class=IntermediateClass.IS,
            opcode_value=5,
            mnemonic="MOVER",
        )
        assert rec.location_counter == 100
        assert rec.statement_class == IntermediateClass.IS


# ---------------------------------------------------------------------------
# Execution models
# ---------------------------------------------------------------------------


class TestRegisterFile:
    def test_defaults_to_zero(self):
        from app.models.execution import RegisterFile
        rf = RegisterFile()
        assert rf.pc == 0
        assert rf.areg == 0

    def test_get_register(self):
        from app.models.execution import RegisterFile
        rf = RegisterFile(areg=42)
        assert rf.get(Register.AREG) == 42

    def test_initial_vm_state_not_halted(self):
        from app.models.execution import VMState
        vm = VMState()
        assert vm.halted is False
        assert vm.status == "NOT_STARTED"


# ---------------------------------------------------------------------------
# Canonical fixture
# ---------------------------------------------------------------------------


class TestCanonicalFixture:
    """Verify the canonical demo program fixture is correct."""

    def test_starts_with_start(self, canonical_source):
        assert canonical_source.strip().startswith("START 100")

    def test_ends_with_end(self, canonical_source):
        assert canonical_source.strip().endswith("END")

    def test_contains_loop_label(self, canonical_source):
        assert "LOOP" in canonical_source

    def test_contains_result_symbol(self, canonical_source):
        assert "RESULT" in canonical_source

    def test_contains_literals(self, canonical_source):
        assert "='5'" in canonical_source
        assert "='1'" in canonical_source
        assert "='2'" in canonical_source

    def test_has_seven_lines(self, canonical_source):
        lines = [l for l in canonical_source.strip().splitlines() if l.strip()]
        assert len(lines) == 7

    def test_passes_request_validation(self, canonical_source):
        from app.models.requests import AnalysisRequest
        req = AnalysisRequest(source_code=canonical_source)
        assert req.source_code == canonical_source.strip()
