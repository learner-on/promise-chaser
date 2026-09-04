"""
test_validation.py
--------------------
Validates reliability_score() using a CONTROLLED SYNTHETIC EXPERIMENT,
since a real-world labeled dataset wasn't available within this project's
timeframe. This is a legitimate, standard validation technique - the
same basic idea used to sanity-check any predictive formula before
real-world data is available: simulate data where you KNOW the true
answer, then check whether your formula can recover it.

BE HONEST WHEN EXPLAINING THIS: this is a synthetic/simulated validation,
not a real-world one. Say so plainly if asked. It still proves something
real - that the formula's logic behaves correctly and isn't just noise -
which is a meaningfully stronger claim than "we never checked."

THE EXPERIMENT, STEP BY STEP:
  1. Create N fake customers, each with a hidden "true_reliability"
     (a number from 0 to 1 - e.g. 0.9 means "90% likely to keep any
     given promise"). This is the ground truth we're trying to recover.
  2. For each customer, SIMULATE a history of promises using their
     true_reliability as a probability (like flipping a biased coin
     for each promise - a coin that lands 'kept' 90% of the time for
     a customer with true_reliability=0.9).
  3. Run our REAL reliability_score() formula on that simulated history
     (the formula never sees true_reliability directly - only the noisy
     coin-flip results, exactly like in real life).
  4. Compare: do customers with HIGHER true_reliability actually get
     HIGHER scores from our formula, on average? We measure this with
     a correlation coefficient (a number from -1 to 1 that says how
     strongly two things move together; close to 1 = strong match).

Run with: python test_validation.py
"""

import random
from scoring import reliability_score

random.seed(42)  # fixed seed = same "random" results every run, so this is reproducible


def simulate_customer_history(true_reliability, num_promises):
    """
    Simulates one customer's promise history. For each promise, we flip
    a biased coin: it lands "kept" with probability = true_reliability.
    This is exactly how you'd simulate a noisy real-world process where
    the underlying tendency is fixed but any single outcome is random.
    """
    return [random.random() < true_reliability for _ in range(num_promises)]


def pearson_correlation(xs, ys):
    """
    Plain-Python Pearson correlation coefficient - no external libraries
    needed. Measures how strongly two lists of numbers move together:
      +1.0 = perfect positive relationship (as one goes up, so does the other)
       0.0 = no relationship at all
      -1.0 = perfect inverse relationship
    """
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    std_x = (sum((x - mean_x) ** 2 for x in xs)) ** 0.5
    std_y = (sum((y - mean_y) ** 2 for y in ys)) ** 0.5

    if std_x == 0 or std_y == 0:
        return 0.0
    return covariance / (std_x * std_y)


def run_validation(num_customers=200, promises_per_customer=6):
    true_reliabilities = []
    computed_scores = []

    for _ in range(num_customers):
        # Ground truth: a random "true" reliability between 5% and 95%
        # (avoiding exact 0 and 1 so the simulation has realistic variety)
        true_rel = random.uniform(0.05, 0.95)

        history = simulate_customer_history(true_rel, promises_per_customer)
        score = reliability_score(history)  # our REAL formula, unchanged

        true_reliabilities.append(true_rel * 100)  # scale to match our 0-100 score
        computed_scores.append(score)

    correlation = pearson_correlation(true_reliabilities, computed_scores)
    return correlation, true_reliabilities, computed_scores


if __name__ == "__main__":
    correlation, truths, scores = run_validation()

    print(f"Ran validation on 200 simulated customers, 6 promises each.\n")
    print(f"Correlation between TRUE reliability and our COMPUTED score: {correlation:.3f}")
    print()

    if correlation > 0.7:
        verdict = "STRONG - the formula reliably recovers the true signal from noisy data."
    elif correlation > 0.4:
        verdict = "MODERATE - the formula captures real signal but with meaningful noise."
    else:
        verdict = "WEAK - the formula may need revisiting."
    print(f"Verdict: {verdict}")

    print("\nSample comparison (first 5 simulated customers):")
    print(f"{'True Reliability':>18} | {'Our Score':>10}")
    for t, s in list(zip(truths, scores))[:5]:
        print(f"{t:>17.1f}% | {s:>9.1f}")

    print(
        "\nNOTE: This is a SYNTHETIC validation (simulated data with known ground\n"
        "truth), not a real-world dataset - real labeled payment-outcome data\n"
        "wasn't available within this project's timeframe. It confirms the\n"
        "formula's logic behaves correctly and isn't just noise, which is a\n"
        "meaningfully stronger claim than having no validation at all."
    )
