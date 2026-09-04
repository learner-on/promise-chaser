"""
scoring.py
----------
This is the "brain" of the project - two scores computed with plain math
(no ML, no external calls). This is the part you should be able to explain
in your sleep for the demo/interview.

1. RELIABILITY SCORE (0-100) - "who is this customer, historically?"
   Based ONLY on their past behavior, not the current invoice.

2. RECOVERY PROBABILITY (0-100%) - "will THIS specific invoice get paid?"
   Based on their reliability score PLUS details of the current invoice
   (how overdue it is, how many times they've already broken a promise
   on this exact invoice).

Why two separate numbers instead of one?
   Reliability = a stable trait about the customer (changes slowly).
   Recovery probability = a live, per-invoice number (changes daily as
   the invoice gets more overdue). Judges/interviewers like this because
   it mirrors how real credit-risk systems separate "customer risk" from
   "transaction risk."
"""


def reliability_score(history):
    """
    history: list of booleans, True = promise kept, False = promise broken
    Returns: score from 0 to 100

    Formula (plain weighted average, no magic):
      - base = % of promises kept, scaled to 0-100
      - recency bonus/penalty: their LAST 2 promises matter more than old ones
        (a customer who used to be bad but has improved recently should score
        better than their raw average suggests - and vice versa)
    """
    if not history:
        return 50  # no data yet -> neutral starting score

    kept = sum(history)
    total = len(history)
    base = (kept / total) * 100

    # Recency weighting: look at the last 2 promises specifically
    recent = history[-2:]
    recent_kept = sum(recent)
    recent_rate = (recent_kept / len(recent)) * 100

    # Blend: 60% overall history, 40% recent behavior
    score = (0.6 * base) + (0.4 * recent_rate)

    return round(score, 1)


def risk_tier(score):
    """Convert a numeric score into a human-readable tier."""
    if score >= 70:
        return "Low"
    elif score >= 40:
        return "Medium"
    else:
        return "High"


def recovery_probability(reliability, days_overdue, broken_promises_on_invoice):
    """
    reliability: the customer's reliability score (0-100)
    days_overdue: how many days past the (latest) promise date
    broken_promises_on_invoice: how many times THIS invoice's promise
                                  has already been broken

    Returns: probability (0-100) that this specific invoice gets paid.

    Real-world pattern this mimics: in collections, the longer an invoice
    stays unpaid, the less likely it ever gets paid (this is a well-known
    curve in accounts receivable - recovery odds drop sharply after ~90 days).
    We approximate that curve with a simple decay formula.
    """
    # Start from their general reliability as the baseline
    prob = reliability

    # Decay based on how overdue this specific invoice is.
    # Every 10 days overdue reduces probability by ~8 points (capped).
    overdue_penalty = min(days_overdue / 10 * 8, 50)
    prob -= overdue_penalty

    # Each broken promise on THIS invoice specifically is a stronger signal
    # than general history - they've now lied about THIS exact debt.
    prob -= broken_promises_on_invoice * 12

    # Clamp between 2 and 98 (never say 0% or 100% - always some uncertainty)
    prob = max(2, min(98, prob))

    return round(prob, 1)


def escalation_action(current_stage, days_overdue):
    """
    Decides what the NEXT action should be, given the current escalation
    stage. This is the "stopping rule" logic the brief explicitly asks for.

    Stage 0 -> 1: Friendly nudge
    Stage 1 -> 2: Firm reminder (only if still unpaid after nudge)
    Stage 2 -> 3: Formal notice
    Stage 3 -> 4: HUMAN HANDOFF - system stops auto-messaging permanently
    Stage 4: no automated action ever again for this invoice
    """
    if current_stage >= 4:
        return {
            "next_stage": 4,
            "action": "human_handoff",
            "tone": None,
            "explanation": "Maximum automated attempts reached. Flagged for human review. No further automated messages will be sent (compliance stopping rule).",
        }

    # Which channel to use for each stage. Plain lookup, same idea as the
    # tone lookup below - just another column of "what to do at this stage."
    # WhatsApp for the first casual nudge (common in Indian B2B), email for
    # anything that needs a formal paper trail, SMS for a short urgent poke.
    stage_map = {
        0: ("nudge", "friendly", "whatsapp"),
        1: ("reminder", "firm", "email"),
        2: ("formal_notice", "formal", "email"),
        3: ("human_handoff", None, None),
    }
    action, tone, channel = stage_map[current_stage]
    next_stage = current_stage + 1

    explanation = f"Escalating from stage {current_stage} to {next_stage} because the promise date has passed and no payment was recorded."

    return {
        "next_stage": next_stage,
        "action": action,
        "tone": tone,
        "channel": channel,
        "explanation": explanation,
    }
