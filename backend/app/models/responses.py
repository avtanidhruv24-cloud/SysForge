"""
SysForge — API response models.

All outgoing response bodies for the ``/api/v1/`` endpoints are defined here.
These wrap stage results with a consistent envelope so the frontend always
receives the same top-level structure regardless of the stage.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from engine.common.enums import AnalysisStage, StageStatus


# ---------------------------------------------------------------------------
# Stage result envelope
# ---------------------------------------------------------------------------


class StageStatusInfo(BaseModel):
    """
    Status metadata for a single pipeline stage.

    Embedded in every analysis response so the frontend knows which stages
    have run, which succeeded, and which are not yet implemented.
    """

    stage: AnalysisStage
    status: StageStatus
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Primary analysis response
# ---------------------------------------------------------------------------


class AnalysisResponse(BaseModel):
    """
    Response body for ``POST /api/v1/analyze``.

    This is the primary contract between the FastAPI backend and the
    ``compilerApi.analyze()`` call in the frozen frontend.

    ``results`` is a flexible dict keyed by ``AnalysisStage`` value.  Each
    value is the serialised stage-specific result (LexerResult, Pass1Result,
    etc.) or ``null`` for stages that have not run.

    This matches the TypeScript type already declared in the frontend::

        type AnalysisResponse = {
          sessionId: string;
          sourceCode: string;
          completedStages: AnalysisStage[];
          results: Partial<Record<AnalysisStage, unknown>>;
        };
    """

    session_id: str = Field(
        description="Unique identifier for this analysis session.",
    )

    source_code: str = Field(
        description="Source code that was analysed (normalised / stripped).",
    )

    completed_stages: list[AnalysisStage] = Field(
        default_factory=list,
        description="Stages that completed successfully.",
    )

    stage_statuses: list[StageStatusInfo] = Field(
        default_factory=list,
        description="Status of every pipeline stage, including un-run ones.",
    )

    results: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Stage-specific results keyed by stage name string "
            "(e.g. 'lexical', 'pass-one').  ``null`` for un-run stages."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "abc123",
                "source_code": "START 100\nMOVER AREG ='5'\nEND",
                "completed_stages": [],
                "stage_statuses": [
                    {
                        "stage": "lexical",
                        "status": "NOT_IMPLEMENTED",
                        "error_count": 0,
                        "warning_count": 0,
                    }
                ],
                "results": {},
            }
        }
    }


# ---------------------------------------------------------------------------
# Health response
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response body for ``GET /api/v1/health``."""

    status: str = Field(default="ok")
    service: str = Field(default="sysforge-backend")
    version: str = Field(default="1.0.0")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "service": "sysforge-backend",
                "version": "1.0.0",
            }
        }
    }


# ---------------------------------------------------------------------------
# Single-stage responses (for the individual stage endpoints)
# ---------------------------------------------------------------------------


class LexResponse(BaseModel):
    """Response for ``POST /api/v1/lex``."""

    session_id: str
    status: StageStatus
    result: Any = Field(
        default=None,
        description="``LexerResult`` or ``null`` if not implemented.",
    )


class ParseResponse(BaseModel):
    """Response for ``POST /api/v1/parse``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)


class MacroResponse(BaseModel):
    """Response for ``POST /api/v1/macro/process``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)


class Pass1Response(BaseModel):
    """Response for ``POST /api/v1/assemble/pass1``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)


class Pass2Response(BaseModel):
    """Response for ``POST /api/v1/assemble/pass2``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)


class LinkResponse(BaseModel):
    """Response for ``POST /api/v1/link``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)


class LoadResponse(BaseModel):
    """Response for ``POST /api/v1/load``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)


class ExecuteResponse(BaseModel):
    """Response for ``POST /api/v1/execute``."""

    session_id: str
    status: StageStatus
    result: Any = Field(default=None)
