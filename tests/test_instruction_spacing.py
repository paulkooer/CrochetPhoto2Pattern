"""Interval claims describe actual cyclic placement, not an average gap."""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.instruction_checks import instruction_issues
from app.models.stitch_notation import StitchExpression, parse_stitch_expression


def _issues(formula, gap, direction):
    expression = parse_stitch_expression(formula)
    assert expression is not None
    counts = expression.counts
    return instruction_issues(
        f"{formula}，隔{gap}针{direction}1针",
        counts.produced, counts.increase, counts.decrease,
        previous_stitches=counts.consumed,
    )


@pytest.mark.parametrize("formula,gap,direction", [
    ("(4X,V,V)×6", 2, "加"),  # Same average gap as the claim, unequal placement.
    ("(4X,A,A)×6", 2, "减"),
    ("(2X,V,X,V)×6", 1, "加"),  # Non-integral average used to skip validation.
    ("(2X,A,X,A)×6", 1, "减"),
    ("V,2X,V,X", 2, "加"),  # Internal gap correct, wraparound gap wrong.
    ("X,A,2X,A", 2, "减"),
    ("((3X,V)×2,X)×3", 3, "加"),  # Gap at a nested repeat boundary.
    ("((3X,A)×2,X)×3", 3, "减"),
    ("6W", 0, "加"),  # W/M changes two stitches per operation, not one.
    ("6M", 0, "减"),
    ("(X,V,A)×6", 3, "加"),  # Opposite shaping is not a plain stitch gap.
    ("(X,V,A)×6", 2, "减"),
    ("BLO((4X,V,V)×6)", 2, "加"),
    ("(4X,inv-sc2tog,inv-sc2tog)×6", 2, "减"),
])
def test_interval_claim_rejects_wrong_positions_even_when_arithmetic_agrees(formula, gap, direction):
    issues = _issues(formula, gap, direction)
    assert issues and all("逐针顺序" in issue for issue in issues)


@pytest.mark.parametrize("formula,gap,direction", [
    ("(2X,V)×6", 2, "加"),
    ("(2X,A)×6", 2, "减"),
    ("(X,V,X)×6", 2, "加"),
    ("(X,A,X)×6", 2, "减"),
    ("V,2X,V,2X", 2, "加"),
    ("((X,A)×2)×3", 1, "减"),
    ("(X)×2,V,(2X,V)×5", 2, "加"),
    ("BLO((X,V,X)×6)", 2, "加"),
    ("sc-FLO,sc-inc-FLO,sc-FLO", 2, "加"),
    ("(X,inv-sc2tog,X)×6", 2, "减"),
    ("4V", 0, "加"),
    ("4A", 0, "减"),
    ("2X,V,3X", 5, "加"),  # A single change also closes across the round start.
    ("(X,V,X)×6", "0" * 5000 + "2", "加"),
])
def test_interval_claim_accepts_equivalent_grouping_rotation_and_loop_techniques(formula, gap, direction):
    assert not _issues(formula, gap, direction)


@pytest.mark.parametrize("formula", ["(X,V,X)×25000", "(2X,V,V)×16000"])
def test_large_interval_check_does_not_expand_stitches(monkeypatch, formula):
    def fail_iteration(self):
        raise AssertionError("checking gaps must not expand stitch repeats")

    monkeypatch.setattr(StitchExpression, "iter_stitches", fail_iteration)
    issues = _issues(formula, 2 if formula.startswith("(X,") else 1, "加")
    assert bool(issues) == formula.startswith("(2X,")


@settings(max_examples=150)
@given(
    groups=st.lists(st.tuples(st.lists(st.sampled_from("XVAWM"), min_size=1, max_size=7),
                              st.integers(1, 4)), min_size=1, max_size=5),
    repeats=st.integers(1, 4), gap=st.integers(0, 6), direction=st.sampled_from(["加", "减"]),
)
def test_compact_check_agrees_with_independent_expanded_circular_gaps(groups, repeats, gap, direction):
    formula = "(" + ",".join(f"({','.join(word)})×{count}" for word, count in groups) + f")×{repeats}"
    word = [symbol for group, count in groups for symbol in group * count] * repeats
    change = "V" if direction == "加" else "A"
    positions = [index for index, symbol in enumerate(word) if symbol == change]
    valid = bool(positions) and set(word) <= {"X", change}
    if valid:
        ends = [*positions[1:], positions[0] + len(word)]
        valid = all(end - start - 1 == gap for start, end in zip(positions, ends, strict=True))
    assert bool(_issues(formula, gap, direction)) == (not valid)
