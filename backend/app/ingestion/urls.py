"""Parse only explicit allowlisted GitHub PR identifiers, without transport."""

import re
from collections.abc import Collection
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.ingestion.models import IngestionError, PullRequestRef, validate_repository


def parse_pr_url(value: str, allowed_repositories: Collection[str]) -> PullRequestRef:
    """Validate raw text before urllib can discard controls or normalize paths."""
    invalid = IngestionError("invalid_pr_url", "Enter a supported GitHub pull request URL.", 400)
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or not value.isascii()
        or any(ord(c) <= 32 or ord(c) == 127 for c in value)
        or any(c in value for c in "%\\?#")
    ):
        raise invalid
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise invalid from None
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not value.startswith("https://github.com/")
    ):
        raise invalid
    match = re.fullmatch(r"/([^/]+)/([^/]+)/pull/([1-9][0-9]*)/?", parsed.path)
    if match is None:
        raise invalid
    try:
        owner, repo, number = match.groups()
        ref = PullRequestRef(owner=owner, repo=repo, number=int(number))
    except (ValidationError, ValueError):
        raise invalid from None
    canonical = f"{ref.owner}/{ref.repo}"
    try:
        allowed = {validate_repository(repository) for repository in allowed_repositories}
    except ValueError:
        allowed = set()  # Invalid injectable configuration must also fail closed.
    if canonical not in allowed:
        raise IngestionError("repository_not_allowed", "This repository is not approved.", 403)
    return ref
