"""Unit tests for the ORCID synchronization script.

This module contains tests for cleaning filenames, retrieving ORCID IDs
from configuration, and fetching works from the ORCID API.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Add scripts directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from orcid_sync import clean_filename, get_orcid_id, fetch_orcid_works

def test_clean_filename() -> None:
    """Test cleaning of strings for use as filenames."""
    assert clean_filename("Hello World!") == "hello-world"
    assert clean_filename("Title with <b>HTML</b>") == "title-with-html"
    assert clean_filename("   Spaces and --- Hyphens   ") == "spaces-and-hyphens"
    assert clean_filename("A" * 200) == ("a" * 100)

def test_get_orcid_id() -> None:
    """Test retrieval of the ORCID ID from the site configuration."""
    config_content = """
author:
  orcid: https://orcid.org/0000-0001-2345-6789
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        assert get_orcid_id() == "0000-0001-2345-6789"

def test_get_orcid_id_none() -> None:
    """Test behavior when the ORCID ID is missing from the configuration."""
    config_content = "author: {}"
    with patch("builtins.open", mock_open(read_data=config_content)):
        assert get_orcid_id() is None

@patch("orcid_sync.requests.get")
def test_fetch_orcid_works(mock_get: MagicMock) -> None:
    """Test fetching work data from the ORCID API."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"group": []}
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    data = fetch_orcid_works("0000-0001-2345-6789")
    assert data == {"group": []}
    mock_get.assert_called_once_with(
        "https://pub.orcid.org/v3.0/0000-0001-2345-6789/works",
        headers={'Accept': 'application/json'}
    )
