"""
test_scoring.py
----------------
Simple, readable tests for scoring.py - no testing framework needed,
just plain Python `assert` statements. This is the minimum "do you test
your code" answer for an interview: not exhaustive, but it proves the
core formulas behave sensibly at their edges.

Run with: python test_scoring.py
If everything passes, it prints "All tests passed." and exits normally.
If anything fails, Python raises an AssertionError showing exactly which
check failed - that's the whole point of using assert directly.
"""

from scoring import reliability_score, risk_tier, recovery_probability, escalation_action


def test_reliability_score_perfect_history():
    # A customer who has kept every promise should score at or near 100
    score = reliability_score([True, True, True, True])
    assert score == 100.0, f"Expected 100.0, got {score}"


def test_reliability_score_all_broken():
    # A customer who has broken every promise should score at or near 0
    score = reliability_score([False, False, False, False])
    assert score == 0.0, f"Expected 0.0, got {score}"


def test_reliability_score_no_history_is_neutral():
    # Brand-new customer with zero history - should NOT be punished or
    # rewarded, just given a neutral starting point
    score = reliability_score([])
    assert score == 50, f"Expected neutral 50 for no history, got {score}"


def test_reliability_score_recent_behavior_matters_more():
    # Two customers with the SAME overall kept-rate (50%), but one has
    # IMPROVED recently and one has gotten WORSE recently. The improved
    # one should score higher, because we weight recent behavior more.
    improved = reliability_score([False, False, True, True])   # bad then good
    worsened = reliability_score([True, True, False, False])   # good then bad
    assert improved > worsened, (
        f"Expected improved customer ({improved}) to score higher than "
        f"worsened customer ({worsened}) despite equal overall history"
    )


def test_risk_tier_boundaries():
    assert risk_tier(85) == "Low"
    assert risk_tier(70) == "Low"     # boundary: exactly 70 is Low
    assert risk_tier(69.9) == "Medium"
    assert risk_tier(40) == "Medium"  # boundary: exactly 40 is Medium
    assert risk_tier(39.9) == "High"
    assert risk_tier(0) == "High"


def test_recovery_probability_never_out_of_bounds():
    # Even in extreme cases, probability must stay within [2, 98] -
    # we never claim absolute certainty in either direction
    very_bad = recovery_probability(reliability=0, days_overdue=999, broken_promises_on_invoice=10)
    very_good = recovery_probability(reliability=100, days_overdue=0, broken_promises_on_invoice=0)
    assert 2 <= very_bad <= 98, f"very_bad probability out of bounds: {very_bad}"
    assert 2 <= very_good <= 98, f"very_good probability out of bounds: {very_good}"
    assert very_good > very_bad, "A reliable, on-time invoice should score higher than a bad one"


def test_recovery_probability_decreases_with_overdue_days():
    # The longer an invoice sits unpaid, the lower its recovery odds -
    # this mirrors a well-known real-world pattern in collections.
    early = recovery_probability(reliability=60, days_overdue=1, broken_promises_on_invoice=0)
    late = recovery_probability(reliability=60, days_overdue=60, broken_promises_on_invoice=0)
    assert early > late, f"Expected earlier invoice ({early}) to have higher probability than late one ({late})"


def test_escalation_stops_at_human_handoff():
    # After stage 3, the NEXT action must always be human_handoff, and it
    # must STAY there forever after - this is the compliance/stopping-rule
    # requirement, so it's the single most important behavior to test.
    result_stage3 = escalation_action(current_stage=3, days_overdue=10)
    assert result_stage3["action"] == "human_handoff"
    assert result_stage3["next_stage"] == 4

    # Calling it again at stage 4 should NEVER escalate further or send
    # another message - it must stay parked at human_handoff.
    result_stage4 = escalation_action(current_stage=4, days_overdue=100)
    assert result_stage4["action"] == "human_handoff"
    assert result_stage4["next_stage"] == 4


def test_escalation_tone_gets_firmer_each_stage():
    # Tone should escalate: friendly -> firm -> formal, never skip or
    # go backwards.
    stage0 = escalation_action(current_stage=0, days_overdue=1)
    stage1 = escalation_action(current_stage=1, days_overdue=5)
    stage2 = escalation_action(current_stage=2, days_overdue=10)
    assert stage0["tone"] == "friendly"
    assert stage1["tone"] == "firm"
    assert stage2["tone"] == "formal"


if __name__ == "__main__":
    tests = [
        test_reliability_score_perfect_history,
        test_reliability_score_all_broken,
        test_reliability_score_no_history_is_neutral,
        test_reliability_score_recent_behavior_matters_more,
        test_risk_tier_boundaries,
        test_recovery_probability_never_out_of_bounds,
        test_recovery_probability_decreases_with_overdue_days,
        test_escalation_stops_at_human_handoff,
        test_escalation_tone_gets_firmer_each_stage,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nAll {len(tests)} tests passed.")
