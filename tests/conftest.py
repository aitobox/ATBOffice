"""Global pytest configuration and shared fixtures for ATBOffice."""

import pytest

from atboffice.core.app import ATBApplication, create_application


@pytest.fixture(scope="session")
def qapp() -> ATBApplication:
    """Provide the ATBApplication singleton for all GUI test fixtures."""
    return create_application([])
