
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
