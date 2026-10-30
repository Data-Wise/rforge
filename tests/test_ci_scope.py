"""Keep release-platform evidence out of ordinary development CI."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


@pytest.mark.parametrize(
    "ref,base_ref,expected",
    [
        ("refs/pull/113/merge", "dev", False),
        ("refs/heads/dev", "", False),
        ("refs/heads/codex/ci-lint-skill", "", False),
        ("refs/pull/114/merge", "main", True),
        ("refs/heads/main", "", True),
    ],
    ids=["dev-pr", "dev-push", "feature-dispatch", "main-pr", "main-ref"],
)
def test_release_platform_jobs_only_run_for_main(ref, base_ref, expected):
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text())
    condition = workflow["jobs"]["a2-release"]["if"]
    # This repository-owned predicate uses comparisons and GitHub's logical OR.
    result = eval(
        condition.replace("||", " or "),
        {"__builtins__": {}, "github": SimpleNamespace(ref=ref, base_ref=base_ref)},
    )
    assert result is expected
