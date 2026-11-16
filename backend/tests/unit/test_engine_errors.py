"""
Unit tests — Engine diagnostic types.

Verifies ``EngineDiagnostic`` and ``DiagnosticBag`` from
``engine.common.errors``.
"""

from __future__ import annotations

import pytest

from engine.common.enums import AnalysisStage
from engine.common.errors import DiagnosticBag, EngineDiagnostic


class TestEngineDiagnostic:
    def test_error_classmethod(self):
        d = EngineDiagnostic.error(
            stage=AnalysisStage.LEXICAL,
            message="unexpected @",
            code="LEXICAL_ERROR",
            line=3,
            column=5,
            token_value="@",
        )
        assert d.severity == "ERROR"
        assert d.is_fatal is True
        assert d.line == 3
        assert d.column == 5
        assert d.token_value == "@"

    def test_warning_classmethod(self):
        d = EngineDiagnostic.warning(
            stage=AnalysisStage.SYNTAX,
            message="possible missing label",
        )
        assert d.severity == "WARNING"
        assert d.is_fatal is False

    def test_location_str_with_both(self):
        d = EngineDiagnostic.error(
            stage=AnalysisStage.LEXICAL,
            message="bad",
            line=4,
            column=2,
        )
        assert "line 4" in d.location_str()
        assert "col 2" in d.location_str()

    def test_location_str_line_only(self):
        d = EngineDiagnostic.error(
            stage=AnalysisStage.LEXICAL,
            message="bad",
            line=7,
        )
        assert "line 7" in d.location_str()

    def test_location_str_unknown(self):
        d = EngineDiagnostic.error(stage=AnalysisStage.LEXICAL, message="bad")
        assert "unknown" in d.location_str()

    def test_str_representation(self):
        d = EngineDiagnostic.error(
            stage=AnalysisStage.LEXICAL,
            message="bad char",
            line=1,
            column=1,
            token_value="@",
        )
        s = str(d)
        assert "ERROR" in s
        assert "bad char" in s
        assert "@" in s

    def test_frozen_dataclass_is_immutable(self):
        d = EngineDiagnostic.error(stage=AnalysisStage.LEXICAL, message="x")
        with pytest.raises(Exception):
            d.message = "changed"  # type: ignore[misc]


class TestDiagnosticBag:
    def test_empty_bag(self):
        bag = DiagnosticBag()
        assert len(bag) == 0
        assert not bag
        assert not bag.has_errors
        assert not bag.has_warnings

    def test_add_error(self):
        bag = DiagnosticBag()
        bag.add_error(AnalysisStage.LEXICAL, "bad", line=1)
        assert bag.has_errors
        assert len(bag) == 1
        assert len(bag.errors) == 1
        assert len(bag.warnings) == 0

    def test_add_warning(self):
        bag = DiagnosticBag()
        bag.add_warning(AnalysisStage.SYNTAX, "heads up", line=2)
        assert bag.has_warnings
        assert not bag.has_errors
        assert len(bag.warnings) == 1

    def test_mixed_bag(self):
        bag = DiagnosticBag()
        bag.add_error(AnalysisStage.LEXICAL, "fatal", line=1)
        bag.add_warning(AnalysisStage.LEXICAL, "warning", line=2)
        assert len(bag) == 2
        assert len(bag.errors) == 1
        assert len(bag.warnings) == 1
        assert bag.has_errors
        assert bag.has_warnings

    def test_add_prebuilt_diagnostic(self):
        bag = DiagnosticBag()
        d = EngineDiagnostic.error(stage=AnalysisStage.SYNTAX, message="x")
        bag.add(d)
        assert len(bag) == 1

    def test_items_returns_copy(self):
        bag = DiagnosticBag()
        bag.add_error(AnalysisStage.LEXICAL, "x")
        items = bag.items
        items.clear()
        assert len(bag) == 1   # original not affected
