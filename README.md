# Promise Chaser — AI Revenue Recovery

## How to run
1. Install dependencies:
   `pip install flask langchain langchain-anthropic --break-system-packages`
2. Run: `python app.py` (creates promise_chaser.db automatically on first run)
3. Open http://localhost:5000
4. Just watch — automation runs on its own every ~12 seconds.

## Run the tests
`python test_scoring.py` — 9 tests on the core scoring/escalation logic
`python test_validation.py` — synthetic validation of the reliability formula (see below)

## Optional: real AI messages / real email
Same as before — set `ANTHROPIC_API_KEY` for real LangChain-generated
messages, and `SENDER_EMAIL` + `SENDER_APP_PASSWORD` (Gmail App Password)
for real SMTP sending. Both safely simulate if not configured.

## File guide (read in this order)
1. db.py               - SQLite persistence layer (see its docstring - explains
                          why/how data is stored, in plain terms)
2. scoring.py           - the "brain": reliability score, recovery probability,
                          escalation rules + channel choice
3. test_scoring.py       - 9 tests proving the scoring/escalation logic behaves
                          correctly, including the compliance-critical one:
                          human handoff can never un-flag itself
4. test_validation.py    - validates reliability_score() against a controlled
                          synthetic experiment (see "On validation" below)
5. message_generator.py  - the ONLY file using AI (LangChain PromptTemplate + chain)
6. email_sender.py       - real SMTP email sending, with safe simulation
7. app.py                - Flask routes + the background automation loop
8. templates/index.html, static/js/app.js, static/css/style.css - UI

## What changed: real persistence (SQLite)
Data used to live in a Python list that reset every time the server
restarted. It now lives in promise_chaser.db, a real SQLite database file
- Python's built-in database engine, no separate install needed. Proven
by test: marking an invoice paid in one Python process, then reading it
back in a completely separate process, correctly shows "paid" - genuine
persistence, not an in-memory illusion.

## On validation (read this before claiming it in an interview)
reliability_score() is validated with a SYNTHETIC controlled experiment,
NOT real-world data - be upfront about that distinction if asked. The
experiment: generate simulated customers with a known "true" reliability,
simulate noisy promise histories from that truth, then check whether the
formula recovers the true signal. Result: 0.784 correlation between true
reliability and the formula's computed score across 200 simulated
customers — a strong result, meaning the formula's logic is sound and
not just noise. This is a real, standard validation technique, just not
a substitute for testing against actual historical payment outcomes,
which wasn't available within the project timeframe.

## The two LangChain concepts used (know these cold)
- PromptTemplate: a reusable prompt with blanks ({customer_name}, etc.)
- Chain: prompt | model | output_parser - pipes steps together like
  terminal piping (cmd1 | cmd2 | cmd3)

## Known, honestly-stated gaps (say these before you're asked)
- Single-tenant, no authentication — fine for a prototype, would need
  auth + per-company data isolation for production
- WhatsApp channel is fully simulated — no real WhatsApp Business API
  integration exists
- Formulas are validated synthetically, not against real payment outcomes

## How to explain this in one breath
Every unpaid invoice from a customer who broke a payment promise gets
scored two ways: a reliability score (validated with a synthetic
experiment showing 0.78 correlation to ground truth) and a recovery
probability specific to the invoice. A background loop checks overdue
invoices on its own, sends an escalating sequence of LangChain-generated
messages via real SMTP where configured, and permanently stops at a
hard 3-attempt limit, handing off to a human — verified by an automated
test, not just claimed. All data persists in a real SQLite database.
Every action, automatic or manual, is logged with a plain-English reason.

## Real bugs I hit and fixed (your "what broke" stories)
1. Flask's debug reloader spawns a watcher process that can hang a
   terminal indefinitely - fixed with use_reloader=False.
2. A missing "Mark as Paid" button on the "Needs Human Attention" section
   meant those invoices were silently unpayable through the UI - found
   by testing, not by inspection, then fixed.
3. An XSS vulnerability - user-typed text (company names) went straight
   into innerHTML unescaped, meaning a malicious name like
   <script>alert(1)</script> would execute in the browser. Fixed with an
   escapeHtml() function applied everywhere user text is displayed.
