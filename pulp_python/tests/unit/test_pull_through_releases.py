from datetime import datetime, timezone

from pulp_python.app.pypi.views import merge_pull_through_releases

UPSTREAM_TIME = datetime(2024, 1, 2, tzinfo=timezone.utc)
CACHED_TIME = datetime(2026, 11, 1, tzinfo=timezone.utc)


def remote_entry(sha256="aaa", yanked=False, yanked_reason="", upload_time=UPSTREAM_TIME):
    return {
        "filename": "pkg-1.0-py3-none-any.whl",
        "url": "https://pulp/pypi/cache/pkg-1.0-py3-none-any.whl?redirect=https://upstream/x",
        "sha256": sha256,
        "upload_time": upload_time,
        "version": "1.0",
        "yanked": yanked,
        "yanked_reason": yanked_reason,
    }


def local_entry(sha256="aaa", yanked=False, yanked_reason=""):
    return {
        "filename": "pkg-1.0-py3-none-any.whl",
        "url": "https://pulp/pypi/cache/pkg-1.0-py3-none-any.whl",
        "sha256": sha256,
        "upload_time": CACHED_TIME,
        "version": "1.0",
        "yanked": yanked,
        "yanked_reason": yanked_reason,
    }


NAME = "pkg-1.0-py3-none-any.whl"


def test_cached_file_keeps_the_remote_upload_time():
    merged = merge_pull_through_releases({NAME: remote_entry()}, {NAME: local_entry()})

    assert merged[NAME]["upload_time"] == UPSTREAM_TIME
    assert merged[NAME]["url"] == local_entry()["url"]


def test_cached_file_yanked_on_the_remote_is_yanked():
    merged = merge_pull_through_releases(
        {NAME: remote_entry(yanked=True, yanked_reason="broken build")}, {NAME: local_entry()}
    )

    assert merged[NAME]["yanked"] is True
    assert merged[NAME]["yanked_reason"] == "broken build"


def test_local_yank_is_kept():
    merged = merge_pull_through_releases(
        {NAME: remote_entry()}, {NAME: local_entry(yanked=True, yanked_reason="ours")}
    )

    assert merged[NAME]["yanked"] is True
    assert merged[NAME]["yanked_reason"] == "ours"


def test_different_file_under_the_same_name_takes_nothing_from_the_remote():
    merged = merge_pull_through_releases(
        {NAME: remote_entry(sha256="bbb", yanked=True)}, {NAME: local_entry()}
    )

    assert merged[NAME] == local_entry()


def test_remote_without_upload_time_keeps_the_local_one():
    merged = merge_pull_through_releases(
        {NAME: remote_entry(upload_time=None)}, {NAME: local_entry()}
    )

    assert merged[NAME]["upload_time"] == CACHED_TIME


def test_files_on_only_one_side_are_listed_unchanged():
    other = {**remote_entry(), "filename": "pkg-2.0.tar.gz"}
    merged = merge_pull_through_releases({"pkg-2.0.tar.gz": other}, {NAME: local_entry()})

    assert merged == {"pkg-2.0.tar.gz": other, NAME: local_entry()}
