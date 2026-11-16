"""
SysForge — Analysis Service.

This is the application-layer orchestrator that sits between the FastAPI
route handlers and the deterministic engine components.

Responsibilities
----------------
1. Create and manage ``AnalysisSession`` objects (in-memory store).
2. Dispatch each requested pipeline stage to its engine component.
3. Update ``StageStatus`` as stages progress.
4. Return ``AnalysisResponse`` objects ready for the API layer to serialise.

Phase status
------------
Phase 3: LEXICAL stage fully implemented (Lexer).
Phase 4: SYNTAX stage fully implemented (Parser).
All other stages return NOT_IMPLEMENTED until their respective phases.

Session store
-------------
Sessions are held in a module-level ``dict`` keyed by ``session_id``.
This is intentionally simple for the educational MVP.  No Redis, no
database, no persistence across restarts.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import NotImplementedError_
from app.models.requests import AnalysisRequest
from app.models.responses import AnalysisResponse, StageStatusInfo
from app.models.sessions import AnalysisSession
from engine.common.enums import AnalysisStage, StageStatus
from engine.assembler import AssemblerPass1
from engine.lexer import Lexer
from engine.parser import Parser

# Module-level engine instances — all are stateless, safe to share.
_lexer = Lexer()
_parser = Parser()
_pass1 = AssemblerPass1()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

# Maps session_id → AnalysisSession.
# Module-level dict is safe for a single-process uvicorn worker.
_sessions: dict[str, AnalysisSession] = {}

# Maximum number of sessions kept in memory at once.
# Oldest sessions are evicted when this limit is reached.
_MAX_SESSIONS = 500

# Canonical pipeline stage order — stages are always run in this sequence
# regardless of the order supplied in the request.
_PIPELINE_ORDER: list[AnalysisStage] = [
    AnalysisStage.LEXICAL,
    AnalysisStage.SYNTAX,
    AnalysisStage.MACRO,
    AnalysisStage.PASS_ONE,
    AnalysisStage.PASS_TWO,
    AnalysisStage.LINKER,
    AnalysisStage.LOADER,
    AnalysisStage.EXECUTION,
    AnalysisStage.AI,
]


# ---------------------------------------------------------------------------
# Session store helpers
# ---------------------------------------------------------------------------


def create_session(source_code: str) -> AnalysisSession:
    """
    Create a new ``AnalysisSession`` for *source_code* and store it.

    Evicts the oldest session when ``_MAX_SESSIONS`` is reached.
    """
    session = AnalysisSession(source_code=source_code)

    if len(_sessions) >= _MAX_SESSIONS:
        oldest_key = next(iter(_sessions))
        _sessions.pop(oldest_key)
        logger.debug("Session store full; evicted session %s", oldest_key)

    _sessions[session.session_id] = session
    logger.debug("Created session %s", session.session_id)
    return session


def get_session(session_id: str) -> AnalysisSession | None:
    """Return the session for *session_id*, or ``None`` if not found."""
    return _sessions.get(session_id)


def session_count() -> int:
    """Return the number of active sessions (for health / monitoring)."""
    return len(_sessions)


# ---------------------------------------------------------------------------
# Stage dispatch
# ---------------------------------------------------------------------------


def _ordered_stages(requested: list[AnalysisStage] | None) -> list[AnalysisStage]:
    """
    Return the stages to run in canonical pipeline order.

    If *requested* is ``None``, return all stages in order.
    Otherwise filter to only the requested stages, preserving order.
    """
    if requested is None:
        return list(_PIPELINE_ORDER)
    requested_set = set(requested)
    return [s for s in _PIPELINE_ORDER if s in requested_set]


def _run_stage(session: AnalysisSession, stage: AnalysisStage) -> None:
    """
    Attempt to run a single pipeline stage.

    Phase 3: LEXICAL stage is fully implemented.
    Phase 4: SYNTAX stage is fully implemented.
    All other stages return NOT_IMPLEMENTED until their respective phases.

    This function updates ``session.stage_statuses`` and sets the
    relevant result field on the session.

    IMPORTANT: Do NOT fabricate results here.  Return only what the
    real engine produces.  If the engine is not built, mark NOT_IMPLEMENTED
    and leave the result field as ``None``.
    """
    session.set_in_progress(stage)
    logger.debug("Running stage '%s' for session %s", stage, session.session_id)

    try:
        # ----------------------------------------------------------------
        # Phase 3 — Lexer  ✅ IMPLEMENTED
        # ----------------------------------------------------------------
        if stage == AnalysisStage.LEXICAL:
            lexer_result = _lexer.analyze(session.source_code)
            session.lexer_result = lexer_result
            error_count = sum(
                1 for d in lexer_result.diagnostics if d.get("severity") == "ERROR"
            )
            warning_count = sum(
                1 for d in lexer_result.diagnostics if d.get("severity") == "WARNING"
            )
            if error_count > 0:
                session.set_error(stage, error_count=error_count)
            else:
                session.set_completed(
                    stage,
                    error_count=error_count,
                    warning_count=warning_count,
                )
            return

        # ----------------------------------------------------------------
        # Phase 4 — Parser  ✅ IMPLEMENTED
        # ----------------------------------------------------------------
        if stage == AnalysisStage.SYNTAX:
            # Parser requires lexer output — run lexer first if needed
            if session.lexer_result is None:
                lexer_result = _lexer.analyze(session.source_code)
                session.lexer_result = lexer_result
                lex_errors = sum(
                    1 for d in lexer_result.diagnostics
                    if d.get("severity") == "ERROR"
                )
                if lex_errors > 0:
                    session.set_error(AnalysisStage.LEXICAL, error_count=lex_errors)
                else:
                    session.set_completed(AnalysisStage.LEXICAL)

            syntax_result = _parser.parse(session.lexer_result)
            session.syntax_result = syntax_result
            error_count = len([
                d for d in syntax_result.diagnostics
                if d.get("severity") == "ERROR"
            ])
            warning_count = len([
                d for d in syntax_result.diagnostics
                if d.get("severity") == "WARNING"
            ])
            if error_count > 0:
                session.set_error(stage, error_count=error_count)
            else:
                session.set_completed(
                    stage,
                    error_count=error_count,
                    warning_count=warning_count,
                )
            return

        # ----------------------------------------------------------------
        # Future — Macro Processor
        # ----------------------------------------------------------------
        if stage == AnalysisStage.MACRO:
            session.set_not_implemented(stage)
            return

        # ----------------------------------------------------------------
        # Phase 5 — Assembler Pass-I  ✅ IMPLEMENTED
        # ----------------------------------------------------------------
        if stage in (
            AnalysisStage.PASS_ONE,
            AnalysisStage.SYMBOLS,
            AnalysisStage.LITERALS,
            AnalysisStage.POOLS,
            AnalysisStage.INTERMEDIATE,
        ):
            # Pass-I requires Parser output — run parser first if needed
            if session.syntax_result is None:
                if session.lexer_result is None:
                    session.lexer_result = _lexer.analyze(session.source_code)
                    lex_errors = sum(
                        1 for d in session.lexer_result.diagnostics
                        if d.get("severity") == "ERROR"
                    )
                    if lex_errors > 0:
                        session.set_error(AnalysisStage.LEXICAL, error_count=lex_errors)
                    else:
                        session.set_completed(AnalysisStage.LEXICAL)

                session.syntax_result = _parser.parse(session.lexer_result)
                parse_errors = sum(
                    1 for d in session.syntax_result.diagnostics
                    if d.get("severity") == "ERROR"
                )
                parse_warnings = sum(
                    1 for d in session.syntax_result.diagnostics
                    if d.get("severity") == "WARNING"
                )
                if parse_errors > 0:
                    session.set_error(AnalysisStage.SYNTAX, error_count=parse_errors)
                else:
                    session.set_completed(
                        AnalysisStage.SYNTAX,
                        error_count=parse_errors,
                        warning_count=parse_warnings,
                    )

            if session.pass1_result is None:
                session.pass1_result = _pass1.assemble(session.syntax_result)

            error_count = sum(
                1 for d in session.pass1_result.diagnostics
                if d.get("severity") == "ERROR"
            )
            warning_count = sum(
                1 for d in session.pass1_result.diagnostics
                if d.get("severity") == "WARNING"
            )
            sub_stages = [
                AnalysisStage.SYMBOLS,
                AnalysisStage.LITERALS,
                AnalysisStage.POOLS,
                AnalysisStage.INTERMEDIATE,
            ]
            if error_count > 0:
                session.set_error(stage, error_count=error_count)
                for sub in sub_stages:
                    session.set_error(sub, error_count=error_count)
            else:
                session.set_completed(
                    stage,
                    error_count=error_count,
                    warning_count=warning_count,
                )
                for sub in sub_stages:
                    session.set_completed(
                        sub,
                        error_count=error_count,
                        warning_count=warning_count,
                    )
            return


        # ----------------------------------------------------------------
        # Phase 4 — Assembler Pass-II
        # ----------------------------------------------------------------
        if stage == AnalysisStage.PASS_TWO:
            session.set_not_implemented(stage)
            return

        # ----------------------------------------------------------------
        # Future — Linker
        # ----------------------------------------------------------------
        if stage == AnalysisStage.LINKER:
            session.set_not_implemented(stage)
            return

        # ----------------------------------------------------------------
        # Future — Loader
        # ----------------------------------------------------------------
        if stage == AnalysisStage.LOADER:
            session.set_not_implemented(stage)
            return

        # ----------------------------------------------------------------
        # Future — Virtual Machine / Execution
        # ----------------------------------------------------------------
        if stage == AnalysisStage.EXECUTION:
            session.set_not_implemented(stage)
            return

        # ----------------------------------------------------------------
        # Future — AI Assistant
        # ----------------------------------------------------------------
        if stage == AnalysisStage.AI:
            session.set_not_implemented(stage)
            return

        # Unknown stage — should not happen if _PIPELINE_ORDER is maintained
        logger.warning("Unknown stage '%s' — skipping", stage)
        session.set_not_implemented(stage)

    except NotImplementedError_ as exc:
        # Re-raised by a future engine component that explicitly signals
        # it is not yet built.
        logger.info("Stage '%s' not implemented: %s", stage, exc)
        session.set_not_implemented(stage)

    except Exception as exc:  # noqa: BLE001
        # Unexpected error — record on session and continue to next stage
        # rather than letting a single broken stage abort the whole run.
        logger.exception("Unexpected error in stage '%s': %s", stage, exc)
        session.set_error(stage, error_count=1)


# ---------------------------------------------------------------------------
# Stage results → response serialisation
# ---------------------------------------------------------------------------


def _collect_results(session: AnalysisSession) -> dict[str, Any]:
    """
    Build the ``results`` dict for the API response.

    Only includes stages that have a non-None result.  Stages that are
    NOT_IMPLEMENTED or have not run are omitted (their status is communicated
    via ``stage_statuses``).
    """
    results: dict[str, Any] = {}

    stage_to_field: dict[AnalysisStage, Any] = {
        AnalysisStage.LEXICAL:      session.lexer_result,
        AnalysisStage.SYNTAX:       session.syntax_result,
        AnalysisStage.MACRO:        session.macro_result,
        AnalysisStage.PASS_ONE:     session.pass1_result,
        # Sub-views of Pass-I (same data, different frontend route)
        AnalysisStage.SYMBOLS:      session.pass1_result,
        AnalysisStage.LITERALS:     session.pass1_result,
        AnalysisStage.POOLS:        session.pass1_result,
        AnalysisStage.INTERMEDIATE: session.pass1_result,
        AnalysisStage.PASS_TWO:     session.pass2_result,
        AnalysisStage.OBJECT_CODE:  session.pass2_result,
        AnalysisStage.LINKER:       session.linker_result,
        AnalysisStage.LOADER:       session.loader_result,
        AnalysisStage.MEMORY:       session.loader_result,
        AnalysisStage.EXECUTION:    session.execution_result,
        AnalysisStage.AI:           session.ai_explain_result,
        AnalysisStage.RESULT:       None,  # synthesised in future
    }

    for stage, result in stage_to_field.items():
        if result is not None:
            results[stage.value] = result.model_dump()

    return results


def _build_stage_statuses(session: AnalysisSession) -> list[StageStatusInfo]:
    """Serialise all stage status entries for the response envelope."""
    return [
        StageStatusInfo(
            stage=entry.stage,
            status=entry.status,
            error_count=entry.error_count,
            warning_count=entry.warning_count,
        )
        for entry in session.stage_statuses.values()
    ]


# ---------------------------------------------------------------------------
# Public API — called by route handlers
# ---------------------------------------------------------------------------


def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Run the full (or partial) SysForge analysis pipeline.

    This is the primary entry point called by ``POST /api/v1/analyze``.

    Steps:
    1. Create a new session.
    2. Determine which stages to run (all, or the requested subset).
    3. Run stages in canonical order, updating session state.
    4. Build and return an ``AnalysisResponse``.

    In Phase 2, every stage returns NOT_IMPLEMENTED.  No fake data is
    produced.  The response is honest: ``completed_stages`` is empty,
    and every ``StageStatusInfo`` reports ``NOT_IMPLEMENTED``.
    """
    session = create_session(request.source_code)
    stages_to_run = _ordered_stages(request.stages)

    logger.info(
        "Analysis started: session=%s stages=%s",
        session.session_id,
        [s.value for s in stages_to_run],
    )

    for stage in stages_to_run:
        _run_stage(session, stage)

    response = AnalysisResponse(
        session_id=session.session_id,
        source_code=session.source_code,
        completed_stages=session.completed_stages,
        stage_statuses=_build_stage_statuses(session),
        results=_collect_results(session),
    )

    logger.info(
        "Analysis complete: session=%s completed=%s",
        session.session_id,
        [s.value for s in response.completed_stages],
    )

    return response


def get_stage_result(session_id: str, stage: AnalysisStage) -> dict[str, Any] | None:
    """
    Return the result dict for a single stage of an existing session.

    Called by ``GET /api/v1/session/{session_id}/{stage}``.
    Returns ``None`` if the session does not exist or the stage has no result.
    """
    session = get_session(session_id)
    if session is None:
        return None

    results = _collect_results(session)
    return results.get(stage.value)


def lex_source(source_code: str) -> tuple[str, "LexerResult"]:
    """
    Run the lexer on *source_code* without creating a full pipeline session.

    Used by ``POST /api/v1/lex`` for lightweight single-stage requests.

    Returns:
        A tuple of (session_id, LexerResult) where session_id is the
        ID of the newly created session (so the caller can cache it).
    """
    from app.models.tokens import LexerResult as _LR  # local import avoids circularity

    session = create_session(source_code)
    lexer_result = _lexer.analyze(source_code)
    session.lexer_result = lexer_result

    error_count = sum(
        1 for d in lexer_result.diagnostics if d.get("severity") == "ERROR"
    )
    warning_count = sum(
        1 for d in lexer_result.diagnostics if d.get("severity") == "WARNING"
    )
    if error_count > 0:
        session.set_error(AnalysisStage.LEXICAL, error_count=error_count)
    else:
        session.set_completed(
            AnalysisStage.LEXICAL,
            error_count=error_count,
            warning_count=warning_count,
        )

    logger.debug(
        "lex_source: session=%s tokens=%d errors=%d",
        session.session_id,
        lexer_result.token_count,
        error_count,
    )
    return session.session_id, lexer_result


def parse_source(source_code: str) -> tuple[str, "SyntaxResult"]:
    """
    Run the lexer then the parser on *source_code* without a full pipeline.

    Used by ``POST /api/v1/parse`` for lightweight single-stage requests.

    Returns:
        A tuple of (session_id, SyntaxResult).
    """
    from app.models.syntax import SyntaxResult as _SR  # avoid circular import

    session = create_session(source_code)

    # Lexer pass
    lexer_result = _lexer.analyze(source_code)
    session.lexer_result = lexer_result
    lex_errors = sum(
        1 for d in lexer_result.diagnostics if d.get("severity") == "ERROR"
    )
    if lex_errors > 0:
        session.set_error(AnalysisStage.LEXICAL, error_count=lex_errors)
    else:
        session.set_completed(AnalysisStage.LEXICAL)

    # Parser pass
    syntax_result = _parser.parse(lexer_result)
    session.syntax_result = syntax_result
    parse_errors = len([
        d for d in syntax_result.diagnostics if d.get("severity") == "ERROR"
    ])
    parse_warnings = len([
        d for d in syntax_result.diagnostics if d.get("severity") == "WARNING"
    ])
    if parse_errors > 0:
        session.set_error(AnalysisStage.SYNTAX, error_count=parse_errors)
    else:
        session.set_completed(
            AnalysisStage.SYNTAX,
            error_count=parse_errors,
            warning_count=parse_warnings,
        )

    logger.debug(
        "parse_source: session=%s statements=%d errors=%d",
        session.session_id,
        syntax_result.statement_count,
        parse_errors,
    )
    return session.session_id, syntax_result


def assemble_pass1_source(source_code: str) -> tuple[str, "Pass1Result"]:
    """
    Run lexer, parser, then assembler Pass-I on *source_code*.

    Used by ``POST /api/v1/assemble/pass1`` for single-stage Pass-I requests.

    Returns:
        A tuple of (session_id, Pass1Result).
    """
    from app.models.assembler import Pass1Result as _P1R

    session = create_session(source_code)

    # 1. Lexer
    lexer_result = _lexer.analyze(source_code)
    session.lexer_result = lexer_result
    lex_errors = sum(
        1 for d in lexer_result.diagnostics if d.get("severity") == "ERROR"
    )
    if lex_errors > 0:
        session.set_error(AnalysisStage.LEXICAL, error_count=lex_errors)
    else:
        session.set_completed(AnalysisStage.LEXICAL)

    # 2. Parser
    syntax_result = _parser.parse(lexer_result)
    session.syntax_result = syntax_result
    parse_errors = sum(
        1 for d in syntax_result.diagnostics if d.get("severity") == "ERROR"
    )
    parse_warnings = sum(
        1 for d in syntax_result.diagnostics if d.get("severity") == "WARNING"
    )
    if parse_errors > 0:
        session.set_error(AnalysisStage.SYNTAX, error_count=parse_errors)
    else:
        session.set_completed(
            AnalysisStage.SYNTAX,
            error_count=parse_errors,
            warning_count=parse_warnings,
        )

    # 3. Assembler Pass-I
    pass1_result = _pass1.assemble(syntax_result)
    session.pass1_result = pass1_result

    pass1_errors = sum(
        1 for d in pass1_result.diagnostics if d.get("severity") == "ERROR"
    )
    pass1_warnings = sum(
        1 for d in pass1_result.diagnostics if d.get("severity") == "WARNING"
    )
    sub_stages = [
        AnalysisStage.SYMBOLS,
        AnalysisStage.LITERALS,
        AnalysisStage.POOLS,
        AnalysisStage.INTERMEDIATE,
    ]
    if pass1_errors > 0:
        session.set_error(AnalysisStage.PASS_ONE, error_count=pass1_errors)
        for sub in sub_stages:
            session.set_error(sub, error_count=pass1_errors)
    else:
        session.set_completed(
            AnalysisStage.PASS_ONE,
            error_count=pass1_errors,
            warning_count=pass1_warnings,
        )
        for sub in sub_stages:
            session.set_completed(
                sub,
                error_count=pass1_errors,
                warning_count=pass1_warnings,
            )

    logger.debug(
        "assemble_pass1_source: session=%s symbols=%d literals=%d pools=%d errors=%d",
        session.session_id,
        len(pass1_result.symbol_table),
        len(pass1_result.literal_table),
        len(pass1_result.pool_table),
        pass1_errors,
    )
    return session.session_id, pass1_result

