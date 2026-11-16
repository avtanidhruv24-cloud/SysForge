"""
SysForge engine — low-level diagnostic types.

This module defines the data structures used by engine components (lexer,
parser, assembler, linker, loader, VM) to report diagnostics.  These are
*value objects* — they carry information but do not raise exceptions by
themselves.

The application layer (``app/services/analysis_service.py``) collects
``EngineDiagnostic`` instances from each stage and decides whether to raise
an ``app.core.errors.SysForgeError`` or return a partial result with
embedded warnings.

Separation of concerns
-----------------------
``engine/common/errors.py``  — pure data; no FastAPI, no HTTP concepts
``app/core/errors.py``       — HTTP-aware exceptions and API error envelopes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.common.enums import AnalysisStage


# ---------------------------------------------------------------------------
# Single diagnostic produced by an engine component
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EngineDiagnostic:
    """
    A single diagnostic message emitted by any engine stage.

    Engine components collect these instead of raising exceptions so that
    analysis can continue past the first error and surface all problems at
    once (e.g. multiple undefined symbols in one assembly run).

    Attributes
    ----------
    stage:
        The pipeline stage that produced this diagnostic.
    message:
        Human-readable description of the problem.
    code:
        Machine-readable code string (mirrors ``ErrorCode`` in
        ``app.core.errors``).  Kept as a plain string here so the engine
        has no import dependency on the API layer.
    severity:
        ``"ERROR"`` for fatal problems, ``"WARNING"`` for non-fatal.
    line:
        1-based source line number.  ``None`` if not applicable.
    column:
        1-based column number.  ``None`` if not applicable.
    token_value:
        The raw token string that triggered the diagnostic, when available.
    details:
        Optional free-form dict for extra structured context.
    """

    stage: AnalysisStage
    message: str
    code: str = "ENGINE_ERROR"
    severity: str = "ERROR"          # "ERROR" | "WARNING" | "INFO"
    line: int | None = None
    column: int | None = None
    token_value: str | None = None
    details: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def error(
        cls,
        stage: AnalysisStage,
        message: str,
        code: str = "ENGINE_ERROR",
        line: int | None = None,
        column: int | None = None,
        token_value: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "EngineDiagnostic":
        """Create a fatal ERROR diagnostic."""
        return cls(
            stage=stage,
            message=message,
            code=code,
            severity="ERROR",
            line=line,
            column=column,
            token_value=token_value,
            details=details,
        )

    @classmethod
    def warning(
        cls,
        stage: AnalysisStage,
        message: str,
        code: str = "ENGINE_WARNING",
        line: int | None = None,
        column: int | None = None,
        token_value: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "EngineDiagnostic":
        """Create a non-fatal WARNING diagnostic."""
        return cls(
            stage=stage,
            message=message,
            code=code,
            severity="WARNING",
            line=line,
            column=column,
            token_value=token_value,
            details=details,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_fatal(self) -> bool:
        """Return ``True`` if this diagnostic is an ERROR."""
        return self.severity == "ERROR"

    def location_str(self) -> str:
        """Human-readable location string, e.g. ``'line 3, col 5'``."""
        if self.line is not None and self.column is not None:
            return f"line {self.line}, col {self.column}"
        if self.line is not None:
            return f"line {self.line}"
        return "unknown location"

    def __str__(self) -> str:
        loc = self.location_str()
        tok = f" (token: '{self.token_value}')" if self.token_value else ""
        return f"[{self.severity}] {self.stage} @ {loc}{tok}: {self.message}"


# ---------------------------------------------------------------------------
# Diagnostic collection helper
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticBag:
    """
    Accumulates ``EngineDiagnostic`` instances during a single stage run.

    Engine components append to a ``DiagnosticBag`` rather than raising
    immediately, allowing analysis to proceed and report multiple errors.

    Usage::

        bag = DiagnosticBag()
        bag.add_error(AnalysisStage.LEXICAL, "Unknown character '@'", line=3)
        if bag.has_errors:
            # surface all errors at once
            ...
    """

    _items: list[EngineDiagnostic] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Adding diagnostics
    # ------------------------------------------------------------------

    def add(self, diagnostic: EngineDiagnostic) -> None:
        """Append a pre-built diagnostic."""
        self._items.append(diagnostic)

    def add_error(
        self,
        stage: AnalysisStage,
        message: str,
        code: str = "ENGINE_ERROR",
        line: int | None = None,
        column: int | None = None,
        token_value: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method: create and append a fatal ERROR."""
        self._items.append(
            EngineDiagnostic.error(
                stage=stage,
                message=message,
                code=code,
                line=line,
                column=column,
                token_value=token_value,
                details=details,
            )
        )

    def add_warning(
        self,
        stage: AnalysisStage,
        message: str,
        code: str = "ENGINE_WARNING",
        line: int | None = None,
        column: int | None = None,
        token_value: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method: create and append a non-fatal WARNING."""
        self._items.append(
            EngineDiagnostic.warning(
                stage=stage,
                message=message,
                code=code,
                line=line,
                column=column,
                token_value=token_value,
                details=details,
            )
        )

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    @property
    def items(self) -> list[EngineDiagnostic]:
        """All collected diagnostics (errors + warnings), in order."""
        return list(self._items)

    @property
    def errors(self) -> list[EngineDiagnostic]:
        """Only fatal ERROR diagnostics."""
        return [d for d in self._items if d.is_fatal]

    @property
    def warnings(self) -> list[EngineDiagnostic]:
        """Only non-fatal WARNING diagnostics."""
        return [d for d in self._items if not d.is_fatal]

    @property
    def has_errors(self) -> bool:
        """``True`` if at least one fatal ERROR has been recorded."""
        return any(d.is_fatal for d in self._items)

    @property
    def has_warnings(self) -> bool:
        """``True`` if at least one WARNING has been recorded."""
        return any(not d.is_fatal for d in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)
