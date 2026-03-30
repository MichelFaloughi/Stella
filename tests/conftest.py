import os
import sys

# Must happen before any project module is imported so LangChain / OpenAI clients
# don't fail on a missing key during collection.
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key-sk-fake")

# Make sure the project root is importable from within the tests/ directory.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mock_calendar_service():
    """Patch tools.calendar.get_service and yield a MagicMock service object."""
    with patch("tools.calendar.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


@pytest.fixture
def mock_gmail_service():
    """Patch tools.gmail.get_service and yield a MagicMock service object."""
    with patch("tools.gmail.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc
