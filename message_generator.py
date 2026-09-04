"""
message_generator.py
---------------------
This is the ONLY file in the whole project that talks to an AI model.
Everything else (scoring, escalation rules) is plain Python logic.

WHAT CHANGED: this now uses LangChain instead of a raw API call. Two
LangChain concepts are used here, and these are the two words to know cold:

  1. PromptTemplate - a reusable prompt with "blanks" in it (like a fill-in-
     the-blanks worksheet). Instead of building a string by hand every time
     with f"...{name}...", you define the template ONCE with placeholders
     like {customer_name}, and LangChain fills them in for you. This makes
     prompts easier to reuse, test, and swap out without touching the
     calling code.

  2. Chain - LangChain's way of connecting steps together with the "|"
     (pipe) operator: prompt | model | output_parser. Here that means:
     "take the filled-in prompt -> send it to Claude -> take the plain
     text out of the response." Each step feeds into the next, just like
     piping commands in a terminal.

WHY ISOLATE AI HERE, SPECIFICALLY: every decision about WHO to message,
WHEN, and WHAT TONE is still plain Python if/else logic in scoring.py.
LangChain is used ONLY to turn that decision into natural-sounding text.
This means you can explain 100% of the "thinking" in the app without any
AI vocabulary, and the AI vocabulary you DO need (PromptTemplate, chain)
is contained to this one file.

SAFE FALLBACK: if no API key is configured, or the API call fails for any
reason, this automatically falls back to a template string instead of
crashing. Demo never breaks on stage.
"""

import os

FALLBACK_TEMPLATES = {
    "friendly": (
        "Hi {name}, hope you're doing well! Just a quick note that invoice "
        "for Rs {amount:,} is still showing as pending on our end. If it's "
        "already been paid, please ignore this - otherwise, would you mind "
        "confirming a new date? Thanks so much!"
    ),
    "firm": (
        "Hi {name}, following up again on the outstanding invoice of "
        "Rs {amount:,}, which is now {days} days past the date we'd agreed on. "
        "Could you please confirm payment status or a firm new date by end "
        "of this week? Let us know if there's an issue we can help resolve."
    ),
    "formal": (
        "Dear {name}, this is a formal notice regarding the unpaid invoice "
        "of Rs {amount:,}, now {days} days overdue after multiple missed "
        "commitments. Please settle this at the earliest to avoid further "
        "escalation, including possible late fees or a hold on future "
        "services. Please contact us directly to resolve this."
    ),
}

# --- LangChain setup -------------------------------------------------------
# This whole block only activates if an API key is present AND the
# langchain packages are installed. Otherwise _chain stays None and we
# silently use the fallback templates above - same safety pattern as before.

_chain = None

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    if os.environ.get("ANTHROPIC_API_KEY"):
        # 1. The PromptTemplate: one reusable template with blanks to fill.
        _prompt = PromptTemplate.from_template(
            """Write a short payment reminder message (3-4 sentences max) to a B2B customer.

Customer name: {customer_name}
Amount owed: Rs {amount}
Days overdue (past their own promised payment date): {days_overdue}
Customer's payment reliability tier: {reliability_tier}
Required tone: {tone} (friendly = warm/assume oversight, firm = clear deadline
no-nonsense, formal = serious/mentions consequences)

Only output the message text, no preamble, no subject line."""
        )

        _model = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=300)

        # 2. The chain: prompt -> model -> plain text.
        #    The "|" pipes the output of one step into the next, same idea
        #    as piping commands in a terminal (cmd1 | cmd2 | cmd3).
        _chain = _prompt | _model | StrOutputParser()

except ImportError:
    _chain = None


def generate_message(customer_name, amount, days_overdue, tone, reliability_tier):
    """
    Builds the recovery message. Tries the LangChain chain first (if
    configured), falls back to a template otherwise - so the demo NEVER
    breaks on stage.
    """
    if _chain is not None:
        try:
            return _chain.invoke({
                "customer_name": customer_name,
                "amount": f"{amount:,}",
                "days_overdue": days_overdue,
                "tone": tone,
                "reliability_tier": reliability_tier,
            }).strip()
        except Exception:
            pass  # fall through to template on any API error

    template = FALLBACK_TEMPLATES.get(tone, FALLBACK_TEMPLATES["friendly"])
    return template.format(name=customer_name, amount=amount, days=days_overdue)
