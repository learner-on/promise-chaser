
import os
import threading
import time
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, render_template, request

import db
from scoring import reliability_score, risk_tier, recovery_probability, escalation_action
from message_generator import generate_message
from email_sender import send_email

app = Flask(__name__)

TODAY = date.today()

# --- Demo-speed automation settings ----------------------------------------
CHECK_INTERVAL_SECONDS = 12   # how often the background loop wakes up
COOLDOWN_SECONDS = 20         # minimum gap between two auto-escalation steps
                               # on the SAME invoice


def days_overdue(promise_date_str):
    promise_date = date.fromisoformat(promise_date_str)
    delta = (TODAY - promise_date).days
    return max(delta, 0)


def enrich_invoice(inv, customer):
    """Attach all computed fields (scores, tier, probability) to a raw invoice."""
    rel_score = reliability_score(customer["history"])
    tier = risk_tier(rel_score)
    overdue = days_overdue(inv["promise_date"]) if inv["status"] == "broken" else 0
    prob = recovery_probability(rel_score, overdue, inv["broken_promises_on_this_invoice"])

    return {
        **inv,
        "customer_name": customer["name"],
        "customer_contact": customer["contact"],
        "customer_industry": customer["industry"],
        "reliability_score": rel_score,
        "risk_tier": tier,
        "days_overdue": overdue,
        "recovery_probability": prob,
    }


def perform_recovery_step(inv, triggered_by="manual"):
    """THE SHARED CORE LOGIC - used by both the manual button and the
    automatic background loop. See scoring.escalation_action() for the
    actual decision rules."""
    customer = db.get_customer(inv["customer_id"])
    decision = escalation_action(inv["escalation_stage"], days_overdue(inv["promise_date"]))

    result = {
        "invoice_id": inv["id"],
        "customer_name": customer["name"],
        "action": decision["action"],
        "channel": decision.get("channel"),
        "explanation": decision["explanation"],
        "message": None,
        "delivery_detail": None,
    }

    if decision["action"] == "human_handoff":
        db.update_invoice(inv["id"], escalation_stage=4)
    else:
        rel_score = reliability_score(customer["history"])
        message = generate_message(
            customer_name=customer["name"],
            amount=inv["amount"],
            days_overdue=days_overdue(inv["promise_date"]),
            tone=decision["tone"],
            reliability_tier=risk_tier(rel_score),
        )
        result["message"] = message

        if decision["channel"] == "email":
            send_result = send_email(
                to_address=customer["contact"],
                subject="Payment Reminder - Outstanding Invoice",
                body=message,
            )
            result["delivery_detail"] = send_result["detail"]
        else:
            result["delivery_detail"] = f"[SIMULATED] Would send via {decision['channel']} to {customer['contact']}."

        db.update_invoice(inv["id"], escalation_stage=decision["next_stage"])

    db.update_invoice(inv["id"], last_action_at=datetime.now().isoformat())

    db.add_log_entry(
        invoice_id=inv["id"],
        customer_name=customer["name"],
        action=decision["action"],
        explanation=decision["explanation"],
        delivery_detail=result["delivery_detail"],
        triggered_by=triggered_by,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    return result


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/invoices")
def api_invoices():
    invoices = db.get_all_invoices()
    enriched = []
    for inv in invoices:
        customer = db.get_customer(inv["customer_id"])
        enriched.append(enrich_invoice(inv, customer))
    return jsonify(enriched)


@app.route("/api/add-company", methods=["POST"])
def api_add_company():
    """Adds a brand-new company + one invoice, saved permanently to the
    database (survives restarts, unlike the old in-memory version)."""
    data = request.get_json()

    name = data.get("name", "").strip()
    industry = data.get("industry", "").strip() or "General Business"
    contact = data.get("contact", "").strip()
    amount = int(data.get("amount", 0))
    promise_days_from_now = int(data.get("promise_days_from_now", 0))
    history_raw = data.get("history", "").strip()
    history = [x.strip() == "1" for x in history_raw.split(",") if x.strip() != ""] if history_raw else []

    if not name or not contact or amount <= 0:
        return jsonify({"error": "Name, contact, and a valid amount are required."}), 400

    customer_id = db.add_customer(name, contact, industry, "N/A", "Net 30", history)

    promise_date = (date.today() + timedelta(days=promise_days_from_now)).isoformat()
    status = "broken" if promise_days_from_now <= 0 else "promised"
    invoice_id = db.add_invoice(
        customer_id=customer_id,
        invoice_no=f"INV/24-25/{1200 + customer_id}",
        description="Manually added for live demo",
        amount=amount,
        due_date=date.today().isoformat(),
        promise_date=promise_date,
        status=status,
    )

    rel_score = reliability_score(history)
    tier = risk_tier(rel_score)
    caution = None
    if rel_score < 40:
        caution = f"⚠️ Caution: {name} has a reliability score of {rel_score}/100 based on their payment history - they have a track record of broken promises. Consider tighter terms or upfront payment."

    db.add_log_entry(
        invoice_id=invoice_id,
        customer_name=name,
        action="invoice_added",
        explanation=f"New invoice manually logged. Reliability score computed as {rel_score}/100 ({tier} risk) from {len(history)} past promise(s).",
        delivery_detail=None,
        triggered_by="manual",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    return jsonify({
        "status": "ok",
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "reliability_score": rel_score,
        "risk_tier": tier,
        "caution": caution,
    })


@app.route("/api/summary")
def api_summary():
    invoices = db.get_all_invoices()
    at_risk = sum(i["amount"] for i in invoices if i["status"] == "broken")
    recovered = sum(i["amount"] for i in invoices if i["status"] == "paid")
    total = sum(i["amount"] for i in invoices)
    broken_count = sum(1 for i in invoices if i["status"] == "broken")
    handoff_count = sum(1 for i in invoices if i["escalation_stage"] >= 4)

    return jsonify({
        "total_amount": total,
        "at_risk_amount": at_risk,
        "recovered_amount": recovered,
        "broken_invoices": broken_count,
        "human_handoff_count": handoff_count,
        "automation_active": True,
        "check_interval_seconds": CHECK_INTERVAL_SECONDS,
    })


@app.route("/api/recover/<int:invoice_id>", methods=["POST"])
def api_recover(invoice_id):
    inv = db.get_invoice(invoice_id)
    result = perform_recovery_step(inv, triggered_by="manual")
    return jsonify(result)


@app.route("/api/simulate-pay/<int:invoice_id>", methods=["POST"])
def api_simulate_pay(invoice_id):
    inv = db.get_invoice(invoice_id)
    customer = db.get_customer(inv["customer_id"])
    db.update_invoice(invoice_id, status="paid")

    db.add_log_entry(
        invoice_id=invoice_id,
        customer_name=customer["name"],
        action="payment_received",
        explanation="Customer paid the outstanding invoice.",
        delivery_detail=None,
        triggered_by="manual",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return jsonify({"status": "ok"})


@app.route("/api/audit-log")
def api_audit_log():
    return jsonify(db.get_all_logs())


@app.route("/api/audit-log/<int:invoice_id>")
def api_audit_log_for_invoice(invoice_id):
    return jsonify(db.get_logs_for_invoice(invoice_id))


# --- Background automation --------------------------------------------------

def background_worker():
    """Runs forever in its own thread - see db.py docstring for how data
    persistence works underneath this."""
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)

        try:
            invoices = db.get_all_invoices()
            for inv in invoices:
                try:
                    if inv["status"] == "promised":
                        promise_date = date.fromisoformat(inv["promise_date"])
                        if TODAY >= promise_date:
                            customer = db.get_customer(inv["customer_id"])
                            db.update_invoice(inv["id"], status="broken")
                            db.add_log_entry(
                                invoice_id=inv["id"],
                                customer_name=customer["name"],
                                action="promise_broken_detected",
                                explanation="Promise date passed with no payment recorded. Invoice automatically marked as at-risk.",
                                delivery_detail=None,
                                triggered_by="automatic",
                                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            )
                            inv["status"] = "broken"  # keep local copy in sync for step 2 below

                    if inv["status"] == "broken" and inv["escalation_stage"] < 4:
                        last = inv.get("last_action_at")
                        if last is None:
                            should_fire = True
                        else:
                            elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                            should_fire = elapsed >= COOLDOWN_SECONDS

                        if should_fire:
                            perform_recovery_step(inv, triggered_by="automatic")

                except Exception as e:
                    print(f"[background_worker] Error processing invoice {inv.get('id')}: {e}")

        except Exception as e:
            print(f"[background_worker] Unexpected error in automation tick: {e}")


def start_background_worker_once():
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        thread = threading.Thread(target=background_worker, daemon=True)
        thread.start()


if __name__ == "__main__":
    db.init_db()
    start_background_worker_once()
    app.run(debug=True, port=5000, use_reloader=False)
