"""
SysForge — Analysis pipeline routes.

Phase 3: POST /api/v1/lex returns real lexer output.
Phase 4: POST /api/v1/parse returns real parser output.
All other stage endpoints remain NOT_IMPLEMENTED stubs until their phases.

Frontend integration point
--------------------------
The frozen frontend's ``compilerApi.analyze()`` posts to::

    POST /api/v1/analyze
    Body: { source_code: str, stages?: str[], options?: object }

The response must match the ``AnalysisResponse`` shape::

    { session_id, source_code, completed_stages, stage_statuses, results }
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, status

from app.core.errors import ErrorCode, ErrorDetail, ErrorResponse, ErrorSeverity
from app.models.requests import AnalysisRequest
from app.models.responses import (
    AnalysisResponse,
    ExecuteResponse,
    LexResponse,
    LinkResponse,
    LoadResponse,
    MacroResponse,
    ParseResponse,
    Pass1Response,
    Pass2Response,
)
from app.services import analysis_service
from engine.common.enums import AnalysisStage, StageStatus

router = APIRouter()

# ---------------------------------------------------------------------------
# Helper: NOT_IMPLEMENTED response factory
# ---------------------------------------------------------------------------


def _not_implemented_response(stage: AnalysisStage, session_id: str = "") -> dict:
    """Return a consistent NOT_IMPLEMENTED envelope for unbuilt endpoints."""
    return {
        "session_id": session_id,
        "status": StageStatus.NOT_IMPLEMENTED,
        "result": None,
    }


# ---------------------------------------------------------------------------
# Primary analysis endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Run full or partial analysis pipeline",
    description=(
        "Submit educational assembly source code to the SysForge pipeline.  "
        "Implemented stages run in canonical order and return real results.  "
        "Stages not yet implemented report ``NOT_IMPLEMENTED`` — no fake data."
    ),
)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Primary entry point called by the frozen frontend's ``compilerApi.analyze()``.

    Phase 3: LEXICAL stage returns real token output.
    Phase 4: SYNTAX stage returns real parsed statement output.
    All other stages still return NOT_IMPLEMENTED.
    """
    return analysis_service.analyze(request)


# ---------------------------------------------------------------------------
# Per-stage endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/lex",
    response_model=LexResponse,
    status_code=status.HTTP_200_OK,
    summary="Lexical analysis only",
    description=(
        "Tokenise the submitted source code and return the full token stream.  "
        "Phase 3: fully implemented."
    ),
)
async def lex(request: AnalysisRequest) -> LexResponse:
    """Run lexical analysis and return real LexerResult."""
    session_id, lexer_result = analysis_service.lex_source(request.source_code)
    stage_status = (
        StageStatus.COMPLETED if lexer_result.success else StageStatus.ERROR
    )
    return LexResponse(
        session_id=session_id,
        status=stage_status,
        result=lexer_result.model_dump(),
    )


@router.post(
    "/parse",
    response_model=ParseResponse,
    status_code=status.HTTP_200_OK,
    summary="Syntax analysis only",
    description=(
        "Parse the submitted source code and return the full statement list.  "
        "Phase 4: fully implemented."
    ),
)
async def parse(request: AnalysisRequest) -> ParseResponse:
    """Run lexical + syntax analysis and return real SyntaxResult."""
    session_id, syntax_result = analysis_service.parse_source(request.source_code)
    stage_status = (
        StageStatus.COMPLETED if syntax_result.success else StageStatus.ERROR
    )
    return ParseResponse(
        session_id=session_id,
        status=stage_status,
        result=syntax_result.model_dump(),
    )


@router.post(
    "/macro/process",
    response_model=MacroResponse,
    status_code=status.HTTP_200_OK,
    summary="Macro processor only",
)
async def macro_process(request: AnalysisRequest) -> MacroResponse:
    """Run only the macro processor stage. Not implemented in Phase 3."""
    return MacroResponse(**_not_implemented_response(AnalysisStage.MACRO))


@router.post(
    "/assemble/pass1",
    response_model=Pass1Response,
    status_code=status.HTTP_200_OK,
    summary="Assembler Pass-I only",
    description=(
        "Perform Assembler Pass-I on the submitted source code.  "
        "Generates SYMTAB, LITTAB, POOLTAB, Intermediate Code, and LC trace.  "
        "Phase 5: fully implemented."
    ),
)
async def assemble_pass1(request: AnalysisRequest) -> Pass1Response:
    """Run lexical + syntax + assembler Pass-I and return real Pass1Result."""
    session_id, pass1_result = analysis_service.assemble_pass1_source(request.source_code)
    stage_status = (
        StageStatus.COMPLETED if pass1_result.success else StageStatus.ERROR
    )
    return Pass1Response(
        session_id=session_id,
        status=stage_status,
        result=pass1_result.model_dump(),
    )



@router.post(
    "/assemble/pass2",
    response_model=Pass2Response,
    status_code=status.HTTP_200_OK,
    summary="Assembler Pass-II only",
)
async def assemble_pass2(request: AnalysisRequest) -> Pass2Response:
    """Run only Assembler Pass-II. Not implemented in Phase 3."""
    return Pass2Response(**_not_implemented_response(AnalysisStage.PASS_TWO))


@router.post(
    "/link",
    response_model=LinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Linker only",
)
async def link(request: AnalysisRequest) -> LinkResponse:
    """Run only the linker stage. Not implemented in Phase 3."""
    return LinkResponse(**_not_implemented_response(AnalysisStage.LINKER))


@router.post(
    "/load",
    response_model=LoadResponse,
    status_code=status.HTTP_200_OK,
    summary="Loader only",
)
async def load(request: AnalysisRequest) -> LoadResponse:
    """Run only the loader stage. Not implemented in Phase 3."""
    return LoadResponse(**_not_implemented_response(AnalysisStage.LOADER))


@router.post(
    "/execute",
    response_model=ExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute via VM",
)
async def execute(request: AnalysisRequest) -> ExecuteResponse:
    """Run only the VM execution stage. Not implemented in Phase 3."""
    return ExecuteResponse(**_not_implemented_response(AnalysisStage.EXECUTION))


# ---------------------------------------------------------------------------
# Session stage retrieval
# ---------------------------------------------------------------------------


@router.get(
    "/session/{session_id}/{stage}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve a single stage result from an existing session",
    description=(
        "Fetch the result for one pipeline stage from a previously created "
        "analysis session.  Corresponds to ``compilerApi.getStage()`` in the "
        "frozen frontend."
    ),
)
async def get_stage(
    session_id: str = Path(description="Session ID returned by /analyze."),
    stage: AnalysisStage = Path(description="Pipeline stage name."),
) -> dict:
    """Return cached stage result for an existing session."""
    result = analysis_service.get_stage_result(session_id, stage)
    if result is None:
        detail = ErrorDetail(
            code=ErrorCode.NOT_IMPLEMENTED,
            message=(
                f"No result available for stage '{stage}' in session "
                f"'{session_id}'. Either the session does not exist or the "
                f"stage has not been run."
            ),
            severity=ErrorSeverity.INFO,
            stage=stage,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(error=detail).model_dump(),
        )
    return result