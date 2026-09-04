# Promise Chaser

A B2B payment recovery system.

The idea: businesses lose money when customers promise to pay by a date and don't, and there's usually no consistent way of tracking or following up on that. This system automates it — it detects broken payment promises, scores how risky the customer is based on their history, and sends an escalating sequence of follow-ups on its own, without anyone needing to check in manually. If it's ignored three times, it stops itself and flags the case for a human instead of continuing to chase.

Built with Python, Flask, SQLite, and LangChain, with real email sending through SMTP. AI is used for exactly one thing - writing the follow-up messages. Everything else, including who gets contacted, how risky they are, and when to stop, runs on plain logic I wrote myself, since I wanted every decision to be explainable rather than hidden inside a model.

The scoring formula is validated against a synthetic dataset with known ground truth (real payment data wasn't available), which showed a 0.78 correlation — a reasonable sanity check, not a substitute for real-world validation. Data persists in a real SQLite database, and the core logic is covered by a small test suite.

Known limitations: single business only, no login/multi-tenant support, and the WhatsApp channel is simulated rather than a real integration.

To run: `pip install flask langchain langchain-anthropic`, then `python app.py`, then open `localhost:5000`.