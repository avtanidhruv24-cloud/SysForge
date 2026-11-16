"""
SysForge — API request models.

All incoming request bodies for the ``/api/v1/`` endpoints are defined here.
These are validated by FastAPI/Pydantic before reaching any service or engine
code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from engine.common.enums import AnalysisStage

# Maximum source code size accepted by the API (characters)
MAX_SOURCE_CHARS: int = 64_000
# Maximum source lines accepted
MAX_SOURCE_LINES: int = 500


class AnalysisOptions(BaseModel):
    """
    Optional per-request configuration for the analysis pipeline.

    Allows the caller to selectively enable / disable stages.
    """

    run_macro_processor: bool = Field(
        default=True,
        description="Whether to run the macro expansion stage.",
    )

    load_address: int = Field(
        default=0,
        ge=0,
        description=(
            "Base address at which the loader places the program in memory.  "
            "Overrides the START directive address when set to a non-zero value."
        ),
    )

    trace_execution: bool = Field(
        default=True,
        description=(
            "When the VM stage runs, collect a full execution trace.  "
            "Disable for very long-running programs to reduce response size."
        ),
    )

    max_execution_steps: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Override the server-side VM_MAX_INSTRUCTIONS limit for this request.  "
            "Cannot exceed the server maximum."
        ),
    )


class AnalysisRequest(BaseModel):
    """
    Request body for ``POST /api/v1/analyze``.

    This is the primary entry point from the frontend.  The ``source_code``
    field holds the raw educational assembly text typed in the source editor.

    ``stages`` lets the caller request only a subset of the pipeline.
    Omitting it (``null``) runs all implemented stages in order.
    """

    source_code: str = Field(
        min_length=1,
        description="Educational assembly source code to analyse.",
    )

    stages: list[AnalysisStage] | None = Field(
        default=None,
        description=(
            "Stages to run.  ``null`` means run the full pipeline.  "
            "Stages are always executed in canonical pipeline order regardless "
            "of the order supplied here."
        ),
    )

    options: AnalysisOptions = Field(
        default_factory=AnalysisOptions,
        description="Optional pipeline configuration.",
    )

    @field_validator("source_code")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source_code must not be empty or whitespace-only.")
        if len(stripped) > MAX_SOURCE_CHARS:
            raise ValueError(
                f"source_code exceeds maximum length of {MAX_SOURCE_CHARS} characters "
                f"(received {len(stripped)})."
            )
        lines = stripped.splitlines()
        if len(lines) > MAX_SOURCE_LINES:
            raise ValueError(
                f"source_code exceeds maximum of {MAX_SOURCE_LINES} lines "
                f"(received {len(lines)})."
            )
        return stripped

    model_config = {
        "json_schema_extra": {
            "example": {
                "source_code": (
                    "START 100\n"
                    "MOVER AREG ='5'\n"
                    "ADD BREG ='1'\n"
                    "LOOP SUB AREG ='2'\n"
                    "MOVEM AREG RESULT\n"
                    "RESULT DS 1\n"
                    "END"
                ),
                "stages": None,
                "options": {"run_macro_processor": True, "load_address": 0},
            }
        }
    }


class StageRequest(BaseModel):
    """
    Request body for individual stage endpoints
    (``/lex``, ``/parse``, ``/assemble/pass1``, etc.).

    Wraps the same source code but targets a single stage.
    """

    source_code: str = Field(min_length=1)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)

    @field_validator("source_code")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source_code must not be empty.")
        if len(stripped) > MAX_SOURCE_CHARS:
            raise ValueError("source_code exceeds maximum length.")
        return stripped


class VMRunRequest(BaseModel):
    """
    Request body for ``POST /api/v1/vm/run`` and ``/vm/step``.

    References an existing analysis session by ID.  The session must have
    a completed ``pass-two`` stage (object code available) before the VM
    can run.
    """

    session_id: str = Field(
        min_length=1,
        description="Session ID returned by a prior ``/analyze`` call.",
    )

    input_data: list[str] = Field(
        default_factory=list,
        description=(
            "Input tokens supplied to READ instructions, in order.  "
            "Each string is one token."
        ),
    )


class AIExplainRequest(BaseModel):
    """Re-exported here for route handler convenience (see app/models/ai.py)."""

    # Import is used from app.models.ai directly — this is a thin re-export
    # kept so route files only need to import from app.models.requests.
    from app.models.ai import AIExplainRequest as _Full  # noqa: F401
