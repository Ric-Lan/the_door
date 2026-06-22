import pytest

from the_door.core.structure_view import locator


def test_load_views_missing_artifacts_raises(tmp_path):
    with pytest.raises(locator.LocateError, match="extract_structure"):
        locator.load_views(tmp_path)
