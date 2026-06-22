from the_door.core.structure_view import chunk_planner as cp


def test_triage_small_no_split():
    assert cp.triage(50, target=100, large_ratio=8) == ("small", False)
    assert cp.triage(100, target=100, large_ratio=8) == ("small", False)  # 邊界 ≤


def test_triage_medium():
    assert cp.triage(101, target=100, large_ratio=8) == ("medium", True)
    assert cp.triage(800, target=100, large_ratio=8) == ("medium", True)  # 邊界 ≤ ratio×


def test_triage_large():
    assert cp.triage(801, target=100, large_ratio=8) == ("large", True)
