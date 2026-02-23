"""
Tests for complexity score calculation.
"""
import pytest
from ..complexity import compute_complexity_score


def test_complexity_zero_parts():
    """Test complexity with zero parts."""
    score = compute_complexity_score(0, 0, 0, None)
    assert score == 0


def test_complexity_simple_assembly():
    """Test complexity with simple assembly."""
    score = compute_complexity_score(5, 5, 0, None)
    assert 0 <= score <= 100
    assert score > 0


def test_complexity_high_parts():
    """Test complexity with many parts."""
    score = compute_complexity_score(100, 50, 0, None)
    assert 0 <= score <= 100
    # Should be higher than simple assembly
    simple_score = compute_complexity_score(5, 5, 0, None)
    assert score > simple_score


def test_complexity_fasteners():
    """Test complexity with fasteners."""
    score_no_fasteners = compute_complexity_score(10, 10, 0, None)
    score_with_fasteners = compute_complexity_score(10, 10, 30, None)
    assert score_with_fasteners > score_no_fasteners


def test_complexity_tree_depth():
    """Test complexity with tree depth."""
    score_no_depth = compute_complexity_score(10, 10, 0, None)
    score_with_depth = compute_complexity_score(10, 10, 0, 5)
    assert score_with_depth > score_no_depth


def test_complexity_unique_ratio():
    """Test complexity with different unique part ratios."""
    score_all_unique = compute_complexity_score(10, 10, 0, None)
    score_some_repeat = compute_complexity_score(10, 5, 0, None)
    # All unique should be higher complexity
    assert score_all_unique > score_some_repeat


def test_complexity_bounds():
    """Test that complexity score is always in valid range."""
    for total in [0, 1, 10, 100, 1000]:
        for unique in [0, 1, total // 2, total]:
            for fasteners in [0, 10, 50, 100]:
                for depth in [None, 0, 5, 10]:
                    score = compute_complexity_score(total, unique, fasteners, depth)
                    assert 0 <= score <= 100, f"Score {score} out of range for total={total}, unique={unique}, fasteners={fasteners}, depth={depth}"
