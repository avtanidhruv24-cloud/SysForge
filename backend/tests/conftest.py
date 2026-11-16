"""
SysForge test suite — shared fixtures and configuration.

This file is loaded automatically by pytest before any test module runs.
All fixtures defined here are available to every test in the suite without
an explicit import.

Fixture catalogue
-----------------
``app``             — FastAPI application instance (test environment)
``client``          — Synchronous ``TestClient`` wrapping the test app
``canonical_source``— The canonical 7-line SysForge demonstration program
``minimal_source``  — Simplest valid program (START + STOP + END)
``analysis_request``— Pre-built ``AnalysisRequest`` using canonical source
``empty_session_store`` — Clears the in-memory session store before/after
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force test environment before any application module is imported.
# This ensures the settings singleton reads APP_ENV=test.
os.environ["APP_ENV"] = "test"
os.environ["HOST"] = "127.0.0.1"
os.environ["PORT"] = "8000"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"


# ---------------------------------------------------------------------------
# App + client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():
    """
    Return the FastAPI application configured for testing.

    ``scope="session"`` means the app is created once for the entire test
    run — this is safe because the app carries no mutable state at the
    module level (sessions are stored separately and cleared per test).
    """
    # Clear the settings cache so APP_ENV=test (set above) is picked up
    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """
    Synchronous ``TestClient`` for the test app.

    ``TestClient`` uses ``requests`` under the hood and can be used in
    plain (non-async) test functions — no ``asyncio`` event loop needed.
    """
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Source code fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def canonical_source() -> str:
    """
    The canonical SysForge demonstration program.

    This is the exact program used throughout the course to illustrate
    every pipeline stage.  It must be stored here — never hard-coded
    inside individual test files.

        START 100
        MOVER AREG ='5'
        ADD BREG ='1'
        LOOP SUB AREG ='2'
        MOVEM AREG RESULT
        RESULT DS 1
        END

    Properties verified by the engine (Phase 3+):
    - START sets LC = 100
    - MOVER AREG ='5' at LC=100 → symbol AREG=1, literal ='5' in pool 0
    - ADD BREG ='1' at LC=101 → literal ='1' in pool 0
    - LOOP defined at LC=102 (SYMTAB: LOOP=102)
    - SUB AREG ='2' at LC=102 → literal ='2' in pool 0
    - MOVEM AREG RESULT at LC=103 → forward ref to RESULT
    - RESULT DS 1 at LC=104 (SYMTAB: RESULT=104)
    - END triggers LTORG: literals ='5','='1','='2' assigned LC=105,106,107
    - LITTAB: [='5'→105, ='1'→106, ='2'→107]
    - POOLTAB: [pool 0 starts at LITTAB index 0]
    """
    return (
        "START 100\n"
        "MOVER AREG ='5'\n"
        "ADD BREG ='1'\n"
        "LOOP SUB AREG ='2'\n"
        "MOVEM AREG RESULT\n"
        "RESULT DS 1\n"
        "END"
    )


@pytest.fixture(scope="session")
def minimal_source() -> str:
    """
    Simplest valid SysForge program: START, STOP, END.

    Useful for testing that a stage does not crash on minimal input.
    """
    return "START 100\nSTOP\nEND"


@pytest.fixture(scope="session")
def multiline_source() -> str:
    """
    A slightly larger program exercising COMP, BC, and a loop.

    Used for parser and assembler tests that need branch instructions.
    """
    return (
        "START 200\n"
        "READ NUM\n"
        "MOVER AREG NUM\n"
        "COMP AREG ='0'\n"
        "BC GT POSITIVE\n"
        "MOVER AREG ='0'\n"
        "POSITIVE PRINT AREG\n"
        "STOP\n"
        "NUM DS 1\n"
        "END"
    )


# ---------------------------------------------------------------------------
# Request model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def analysis_request(canonical_source: str):
    """
    Pre-built ``AnalysisRequest`` using the canonical source.

    ``scope`` is function-level (default) so each test gets a fresh object.
    """
    from app.models.requests import AnalysisRequest
    return AnalysisRequest(source_code=canonical_source)


@pytest.fixture
def minimal_request(minimal_source: str):
    """Pre-built ``AnalysisRequest`` using the minimal source."""
    from app.models.requests import AnalysisRequest
    return AnalysisRequest(source_code=minimal_source)


# ---------------------------------------------------------------------------
# Session store isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_session_store():
    """
    Clear the in-memory session store before and after every test.

    ``autouse=True`` means this runs for every test automatically.
    This prevents sessions created in one test from bleeding into another.
    """
    from app.services import analysis_service
    analysis_service._sessions.clear()
    yield
    analysis_service._sessions.clear()
