"""Release version transitions are independent of GitHub publication."""

import pytest

from scripts.bump_plugin_version import bump


@pytest.mark.parametrize(("level", "expected"), [("patch", "0.32.1"), ("minor", "0.33.0"), ("major", "1.0.0")])
def test_release_bump(level, expected):
    assert bump("0.32.0", level) == expected


def test_refuses_non_stable_version():
    with pytest.raises(ValueError):
        bump("1.0.0-rc.1", "patch")
