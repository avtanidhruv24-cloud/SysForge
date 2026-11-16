"""
SysForge — AnalysisSession model.

An ``AnalysisSession`` is the central data container that travels through
the entire SysForge pipeline.  It is created when the frontend submits a
``POST /api/v1/analyze`` request and is updated by each engine stage as it
completes.

Design decisions
----------------
- Every stage field is ``Optional`` — stages that have not run are ``None``.
- A ``stage_statuses`` dict records the lifecycle of each stage so the
  frontend can report "WAITING", "COMPLETED", or "ERROR" per stage.
- The session is held in-memory (a simple dict keyed by ``session_id``).
  No database is required for the educational MVP.
- Sessions are immutable in the sense that completed stage results are
  never overwritten; only the status of pending stages changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.assembler import (
    LiteralTableEntry,
    MacroResult,
    Pass1Result,
    Pass2Result,
    PoolTableEntry,
    SymbolTableEntry,
)
from app.models.ai import AIOptimizeResponse, AIExplainResponse
from app.models.execution import ExecutionResult
from app.models.linking import LinkerResult, LoaderResult
from app.models.syntax import SyntaxResult
from app.models.tokens import LexerResult
from engine.common.enums import AnalysisStage, StageStatus


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _new_session_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Per-stage status entry
# ---------------------------------------------------------------------------


class StageStatusEntry(BaseModel):
    """
    Tracks the lifecycle of a single pipeline stage within a session.

    Stored in ``AnalysisSession.stage_statuses``.
    """

    stage: AnalysisStage
    status: StageStatus = StageStatus.NOT_STARTED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_count: int = 0
    warning_count: int = 0

    def mark_in_progress(self) -> None:
        self.status = StageStatus.IN_PROGRESS
        self.started_at = _utc_now()

    def mark_completed(
        self, error_count: int = 0, warning_count: int = 0
    ) -> None:
        self.status = StageStatus.COMPLETED
        self.completed_at = _utc_now()
        self.error_count = error_count
        self.warning_count = warning_count

    def mark_error(self, error_count: int = 1) -> None:
        self.status = StageStatus.ERROR
        self.completed_at = _utc_now()
        self.error_count = error_count

    def mark_not_implemented(self) -> None:
        self.status = StageStatus.NOT_IMPLEMENTED

    @property
    def is_done(self) -> bool:
        """``True`` if the stage has finished (completed or errored)."""
        return self.status in (StageStatus.COMPLETED, StageStatus.ERROR)


# ---------------------------------------------------------------------------
# AnalysisSession
# ---------------------------------------------------------------------------


def _default_stage_statuses() -> dict[str, StageStatusEntry]:
    """Initialise every known stage as NOT_STARTED."""
    return {
        stage.value: StageStatusEntry(stage=stage)
        for stage in AnalysisStage
    }


class AnalysisSession(BaseModel):
    """
    Central data container for one complete SysForge analysis run.

    Lifecycle
    ---------
    1. Created by ``AnalysisService.create_session(source_code)``
    2. Each engine stage reads from and writes to this object
    3. The API layer serialises it into ``AnalysisResponse`` for the frontend

    Fields set by the API layer
    ---------------------------
    - ``session_id``  — UUID hex, used by the frontend for ``getStage`` calls
    - ``source_code`` — normalised assembly source
    - ``created_at``  — UTC timestamp

    Fields populated by engine stages (all Optional)
    ------------------------------------------------
    - ``lexer_result``        — output of the Lexer
    - ``syntax_result``       — output of the Parser
    - ``macro_result``        — output of the Macro Processor
    - ``pass1_result``        — output of Assembler Pass-I (contains all four artifacts)
    - ``pass2_result``        — output of Assembler Pass-II (object code)
    - ``linker_result``       — output of the Linker
    - ``loader_result``       — output of the Loader (memory map)
    - ``execution_result``    — output of the Virtual Machine
    - ``ai_explain_result``   — most recent AI explanation response
    - ``ai_optimize_result``  — most recent AI optimisation response

    Convenience accessors (derived from pass1_result)
    -------------------------------------------------
    Use ``.symbol_table``, ``.literal_table``, ``.pool_table`` to access
    the Pass-I sub-artifacts without traversing the full pass1_result.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    session_id: str = Field(default_factory=_new_session_id)
    created_at: datetime = Field(default_factory=_utc_now)
    source_code: str = Field(default="")

    # ------------------------------------------------------------------
    # Stage lifecycle tracking
    # ------------------------------------------------------------------

    stage_statuses: dict[str, StageStatusEntry] = Field(
        default_factory=_default_stage_statuses,
        description="Status of each pipeline stage keyed by stage name string.",
    )

    # ------------------------------------------------------------------
    # Stage results (all Optional — None means stage has not run)
    # ------------------------------------------------------------------

    lexer_result: LexerResult | None = Field(
        default=None,
        description="Tokens and lexical diagnostics.  None until lexer runs.",
    )

    syntax_result: SyntaxResult | None = Field(
        default=None,
        description="Parsed statements and syntax diagnostics.",
    )

    macro_result: MacroResult | None = Field(
        default=None,
        description="Macro definitions, calls, and expanded source.",
    )

    pass1_result: Pass1Result | None = Field(
        default=None,
        description="SYMTAB, LITTAB, POOLTAB, and Intermediate Code.",
    )

    pass2_result: Pass2Result | None = Field(
        default=None,
        description="Object / machine code words.",
    )

    linker_result: LinkerResult | None = Field(
        default=None,
        description="Linked module with resolved addresses.",
    )

    loader_result: LoaderResult | None = Field(
        default=None,
        description="Loaded memory map and entry point.",
    )

    execution_result: ExecutionResult | None = Field(
        default=None,
        description="VM execution trace, final state, and program output.",
    )

    ai_explain_result: AIExplainResponse | None = Field(
        default=None,
        description="Most recent AI explanation response.",
    )

    ai_optimize_result: AIOptimizeResponse | None = Field(
        default=None,
        description="Most recent AI optimisation response.",
    )

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def symbol_table(self) -> list[SymbolTableEntry]:
        """SYMTAB from Pass-I, or empty list if Pass-I has not run."""
        return self.pass1_result.symbol_table if self.pass1_result else []

    @property
    def literal_table(self) -> list[LiteralTableEntry]:
        """LITTAB from Pass-I, or empty list."""
        return self.pass1_result.literal_table if self.pass1_result else []

    @property
    def pool_table(self) -> list[PoolTableEntry]:
        """POOLTAB from Pass-I, or empty list."""
        return self.pass1_result.pool_table if self.pass1_result else []

    @property
    def completed_stages(self) -> list[AnalysisStage]:
        """List of stages that have status COMPLETED."""
        return [
            AnalysisStage(stage_name)
            for stage_name, entry in self.stage_statuses.items()
            if entry.status == StageStatus.COMPLETED
        ]

    @property
    def has_errors(self) -> bool:
        """``True`` if any stage has status ERROR."""
        return any(
            entry.status == StageStatus.ERROR
            for entry in self.stage_statuses.values()
        )

    # ------------------------------------------------------------------
    # Stage status helpers
    # ------------------------------------------------------------------

    def get_status(self, stage: AnalysisStage) -> StageStatusEntry:
        """Return the status entry for the given stage."""
        return self.stage_statuses[stage.value]

    def set_in_progress(self, stage: AnalysisStage) -> None:
        self.stage_statuses[stage.value].mark_in_progress()

    def set_completed(
        self,
        stage: AnalysisStage,
        error_count: int = 0,
        warning_count: int = 0,
    ) -> None:
        self.stage_statuses[stage.value].mark_completed(error_count, warning_count)

    def set_error(self, stage: AnalysisStage, error_count: int = 1) -> None:
        self.stage_statuses[stage.value].mark_error(error_count)

    def set_not_implemented(self, stage: AnalysisStage) -> None:
        self.stage_statuses[stage.value].mark_not_implemented()

    # ------------------------------------------------------------------
    # Pydantic config
    # ------------------------------------------------------------------

    model_config = {"arbitrary_types_allowed": True}
