"""
SysForge — AI Assistant domain models.

These are the contracts for the ``/ai`` frontend view.

Architecture reminder
---------------------
AI must NEVER be the assembler/compiler.  Every AI request must include
deterministic engine context (the stage result that exists in the
``AnalysisSession``).  The AI service only *explains* or *suggests*; it
never *produces* SYMTAB entries, machine words, memory maps, etc.

The ``context`` field on ``AIExplainRequest`` carries a slice of the
deterministic result so the LLM has grounded, factual material to work from.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.common.enums import AnalysisStage


# ---------------------------------------------------------------------------
# AI Explain
# ---------------------------------------------------------------------------


class AIExplainRequest(BaseModel):
    """
    Request body for ``POST /api/v1/ai/explain``.

    The ``context_item`` carries the specific artifact the user clicked on
    (a token, a SYMTAB row, an intermediate record, etc.) serialised as a
    plain dict — the AI service is schema-agnostic at this level.
    """

    session_id: str = Field(
        description="Active analysis session the explanation is grounded in."
    )

    stage: AnalysisStage = Field(
        description="The pipeline stage whose output is being explained.",
    )

    question: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "The user's question, e.g. "
            "'Why was this symbol assigned this address?' "
            "or 'Explain this literal pool'."
        ),
    )

    context_item: dict | None = Field(
        default=None,
        description=(
            "The specific artifact being explained, serialised from the "
            "deterministic engine result.  The AI may not invent values "
            "not present here or in the session."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "a1b2c3d4",
                "stage": "symbols",
                "question": "Why was LOOP assigned address 104?",
                "context_item": {"name": "LOOP", "value": 104, "defined_at_line": 4},
            }
        }
    }


class AIExplainResponse(BaseModel):
    """Response from ``POST /api/v1/ai/explain``."""

    explanation: str = Field(
        description="AI-generated explanation grounded in the provided context."
    )

    confidence: str = Field(
        default="HIGH",
        description="Confidence level: 'HIGH', 'MEDIUM', or 'LOW'.",
    )

    referenced_stage: AnalysisStage = Field(
        description="The stage the explanation refers to.",
    )

    sources: list[str] = Field(
        default_factory=list,
        description=(
            "List of deterministic context references used by the AI "
            "(e.g. 'SYMTAB[LOOP].value = 104')."
        ),
    )

    session_id: str = Field(description="Session ID echoed from the request.")


# ---------------------------------------------------------------------------
# AI Optimisation
# ---------------------------------------------------------------------------


class OptimizationSuggestion(BaseModel):
    """
    A single optimisation suggestion returned by the AI service.

    Suggestions are advisory only.  The source code is never changed
    without explicit user action.

    Frontend column mapping (``/ai`` optimize tab):
        Description       → description
        Target line       → target_line
        Suggested change  → suggested_change
        Rationale         → rationale
    """

    description: str = Field(
        description="Short description of the suggested improvement.",
    )

    target_line: int | None = Field(
        default=None,
        ge=1,
        description="1-based source line the suggestion applies to.",
    )

    suggested_change: str | None = Field(
        default=None,
        description="Proposed replacement source text, if applicable.",
    )

    rationale: str = Field(
        description="Explanation of *why* this change would improve the program.",
    )

    category: str = Field(
        default="general",
        description=(
            "Optimisation category: 'register-usage', 'literal-elimination', "
            "'branch-reduction', 'storage-efficiency', 'general'."
        ),
    )

    is_safe: bool = Field(
        default=True,
        description=(
            "``True`` if the suggested change preserves program semantics.  "
            "``False`` for suggestions that trade correctness for speed."
        ),
    )


class AIOptimizeRequest(BaseModel):
    """Request body for ``POST /api/v1/ai/optimize``."""

    session_id: str = Field(
        description="Active analysis session to analyse for optimisations.",
    )


class AIOptimizeResponse(BaseModel):
    """Response from ``POST /api/v1/ai/optimize``."""

    suggestions: list[OptimizationSuggestion] = Field(
        default_factory=list,
        description="Ordered list of optimisation suggestions.",
    )

    summary: str = Field(
        default="",
        description="Overall programme quality summary from the AI service.",
    )

    session_id: str = Field(description="Session ID echoed from the request.")
