"""Construct public permalinks only from independently validated pinned evidence."""

from typing import Literal
from urllib.parse import quote

from app.ingestion.models import PinnedPullRequest, SourceReference, validate_path


def source_reference(
    metadata: PinnedPullRequest,
    revision: Literal["base", "head"],
    file_path: str,
    start_line: int,
    end_line: int,
) -> SourceReference:
    """Use analysis-base provenance for deletions and head provenance for additions."""
    metadata = PinnedPullRequest.model_validate(metadata.model_dump())
    if revision not in ("base", "head"):
        raise ValueError("invalid source revision")
    validate_path(file_path)
    repository = metadata.base_repository if revision == "base" else metadata.head_repository
    sha = metadata.analysis_base_sha if revision == "base" else metadata.head_sha
    ref = SourceReference(
        revision=revision, repository=repository, commit_sha=sha, file_path=file_path,
        start_line=start_line, end_line=end_line, url="",
    )
    path = "/".join(quote(segment, safe="") for segment in file_path.split("/"))
    anchor = f"L{start_line}" if start_line == end_line else f"L{start_line}-L{end_line}"
    return ref.model_copy(update={"url": f"https://github.com/{repository}/blob/{sha}/{path}#{anchor}"})
