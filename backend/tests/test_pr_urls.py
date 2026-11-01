"""Admission must reject unsafe identifiers without any network activity."""

import pytest
from pydantic import ValidationError

from app.ingestion.models import IngestionError
from app.ingestion.settings import Limits, Settings
from app.ingestion.urls import parse_pr_url


@pytest.mark.parametrize("suffix", ["", "/"])
def test_allowed_url_is_canonical(suffix):
    ref = parse_pr_url("https://github.com/Owner/Repo/pull/12" + suffix, {"OWNER/REPO"})
    assert (ref.owner, ref.repo, ref.number) == ("owner", "repo", 12)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/o/r/pull/1",
        "https://www.github.com/o/r/pull/1",
        "https://api.github.com/o/r/pull/1",
        "https://github.com.evil/o/r/pull/1",
        "https://user@github.com/o/r/pull/1",
        "https://github.com:443/o/r/pull/1",
        "https://github.com/o/r/pull/0",
        "https://github.com/o/r/pull/-1",
        "https://github.com/o/r/pull/1?x=y",
        "https://github.com/o/r/pull/1?",
        "https://github.com/o/r/pull/1#x",
        "https://github.com/o/r/pull/1#",
        "https://github.com/o/r/pull/1/files",
        "https://github.com/o/r/pull/1//",
        "https://github.com/o/r%2fp/pull/1",
        "https://github.com/o/%72/pull/1",
        "https://github.com/o/../r/pull/1",
        "https://github.com/o/./pull/1",
        "https://github.com/o//r/pull/1",
        "https://github.com/o\\r/pull/1",
        "https://github.com/-o/r/pull/1",
        "https://github.com/o-/r/pull/1",
        "https://github.com/o--p/r/pull/1",
        "https://github.com/ö/r/pull/1",
        "https://github.com/o/./pull/1",
        "https://github.com/o/../pull/1",
        "https://github.com/o/r/pull/１",
        "https://github.com/o/r/pull/+1",
        " https://github.com/o/r/pull/1",
        "https://github.com/o/r/pull/1\n",
        "https://github.com/o/\tr/pull/1",
        "https://github.com/o/r/pull/1\x00",
        "https://github.com/" + "o" * 40 + "/r/pull/1",
        "https://github.com/o/" + "r" * 101 + "/pull/1",
        "https://github.com/o/r/pull/" + "1" * 2050,
    ],
)
def test_reject_url_matrix(url):
    with pytest.raises(IngestionError) as caught:
        parse_pr_url(url, {"o/r"})
    assert caught.value.code == "invalid_pr_url"
    assert url not in caught.value.public_message


def test_allowlist_exact_membership():
    for allowed in (set(), {"o/r-other"}, {"other/r"}):
        with pytest.raises(IngestionError) as caught:
            parse_pr_url("https://github.com/o/r/pull/1", allowed)
        assert caught.value.code == "repository_not_allowed"


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"GITHUB_TOKEN": "upstream"},
        {"CODESCOPE_ALLOWED_REPOSITORIES": "o/r"},
        {"CODESCOPE_LIVE_ACCESS_TOKEN": "caller"},
        {"CODESCOPE_ALLOWED_REPOSITORIES": "o/r", "CODESCOPE_LIVE_ACCESS_TOKEN": "   "},
    ],
)
def test_missing_access_configuration_disables_live(environment):
    settings = Settings.from_env(environment)
    assert not settings.live_enabled
    with pytest.raises(IngestionError) as caught:
        settings.require_live_enabled()
    assert caught.value.code == "live_analysis_disabled"


def test_distinct_credentials_and_secret_representations():
    settings = Settings.from_env(
        {
            "CODESCOPE_ALLOWED_REPOSITORIES": "Owner/Repo,other/repo",
            "CODESCOPE_LIVE_ACCESS_TOKEN": "caller-secret",
            "GITHUB_TOKEN": "upstream-secret",
        }
    )
    assert settings.live_enabled
    settings.require_live_enabled()
    assert settings.allowed_repositories == frozenset({"owner/repo", "other/repo"})
    assert settings.live_access_token.get_secret_value() == "caller-secret"
    assert settings.github_token.get_secret_value() == "upstream-secret"
    assert "caller-secret" not in repr(settings)
    assert "upstream-secret" not in settings.model_dump_json()


@pytest.mark.parametrize("allowlist", ["https://github.com/o/r", "o/*", "o/r,", "../r", "o/r/x"])
def test_invalid_config_fails_closed(allowlist):
    with pytest.raises(ValueError):
        Settings.from_env(
            {"CODESCOPE_ALLOWED_REPOSITORIES": allowlist, "CODESCOPE_LIVE_ACCESS_TOKEN": "caller"}
        )


def test_limits_immutable_and_environment_only_lowers():
    limits = Limits()
    assert limits.analysis_timeout_seconds == 60
    assert limits.http_timeout_seconds == 10
    assert limits.max_http_requests == 200
    assert limits.max_json_bytes == 2 * 1024**2
    assert limits.max_tree_entries == 2000
    assert limits.max_changed_files == limits.max_python_files_per_revision == 100
    assert limits.max_source_file_bytes == 128 * 1024
    assert limits.max_total_source_bytes == 8 * 1024**2
    assert limits.max_summary_bytes == 2 * 1024**2
    assert limits.max_terminal_records == 20
    assert limits.terminal_ttl_seconds == 3600
    assert limits.max_active_analyses == 1
    with pytest.raises(ValidationError):
        limits.max_http_requests = 100
    with pytest.raises(ValidationError):
        Settings().allowed_repositories = frozenset({"o/r"})
    for field, value in limits.model_dump().items():
        for invalid in (0, value + 1):
            with pytest.raises(ValueError):
                Settings.from_env({"CODESCOPE_" + field.upper(): str(invalid)})
    lower = Settings.from_env(
        {"CODESCOPE_MAX_HTTP_REQUESTS": "50", "CODESCOPE_ANALYSIS_TIMEOUT_SECONDS": "5"}
    )
    assert lower.limits.max_http_requests == 50
    assert lower.limits.analysis_timeout_seconds == 5
    with pytest.raises(ValidationError):
        Limits(max_http_requests=201)
