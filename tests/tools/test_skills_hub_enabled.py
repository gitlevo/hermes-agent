"""mooxi patch: ``skills.hub_enabled: false`` leaves the skills hub with no source (MOOXI-PATCHES.md).

Every hub search, install, update and check builds its sources with ``create_source_router``, so an empty
router means nothing can come from a registry. Default (true) is upstream."""

import pytest

import hermes_cli.config as config
from tools import skills_hub_search


@pytest.fixture
def hub(monkeypatch):
    def set_enabled(value):
        skills = {} if value is None else {"hub_enabled": value}
        monkeypatch.setattr(config, "load_config", lambda: {"skills": skills})
    return set_enabled


def test_off_means_no_sources(hub):
    hub(False)
    assert skills_hub_search.create_source_router() == []


def test_unset_keeps_every_source(hub):
    hub(None)
    names = {type(s).__name__ for s in skills_hub_search.create_source_router()}
    assert {"UrlSource", "ClawHubSource", "GitHubSource"} <= names


def test_search_finds_nothing_when_off(hub):
    hub(False)
    assert skills_hub_search.unified_search("pdf", skills_hub_search.create_source_router(), limit=5) == []
