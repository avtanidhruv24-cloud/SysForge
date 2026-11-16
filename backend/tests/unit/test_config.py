"""
Unit tests — Settings / configuration.

Verifies that the settings object correctly resolves defaults and that
environment variable overrides are respected.
"""

from __future__ import annotations

import pytest


class TestSettingsDefaults:
    """Settings resolve correct defaults when no .env file is present."""

    def test_api_prefix_is_versioned(self):
        from app.core.config import get_settings
        s = get_settings()
        assert s.api_prefix == "/api/v1"

    def test_app_version_is_set(self):
        from app.core.config import get_settings
        assert get_settings().app_version == "1.0.0"

    def test_app_title_is_set(self):
        from app.core.config import get_settings
        assert "SysForge" in get_settings().app_title

    def test_cors_origins_is_list(self):
        from app.core.config import get_settings
        assert isinstance(get_settings().cors_origins, list)
        assert len(get_settings().cors_origins) >= 1

    def test_default_cors_includes_vite_port(self):
        from app.core.config import get_settings
        joined = " ".join(get_settings().cors_origins)
        assert "5173" in joined

    def test_vm_limits_are_positive(self):
        from app.core.config import get_settings
        s = get_settings()
        assert s.vm_max_instructions > 0
        assert s.vm_max_memory_words > 0
        assert s.vm_max_output_lines > 0
        assert s.vm_execution_timeout_seconds > 0

    def test_app_env_is_test(self):
        """APP_ENV was set to 'test' in conftest.py before import."""
        from app.core.config import get_settings
        assert get_settings().app_env == "test"

    def test_is_test_property(self):
        from app.core.config import get_settings
        s = get_settings()
        assert s.is_test is True
        assert s.is_production is False
