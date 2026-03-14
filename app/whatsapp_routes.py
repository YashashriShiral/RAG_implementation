"""
app/whatsapp_routes.py
────────────────────────────────────────────────────────────────────────────
FastAPI WhatsApp webhook via Twilio.
"""

import os, traceback
from dotenv import load_dotenv
from fastapi import APIRouter, Form, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from loguru import logger

load_dotenv()

TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
USER_NUMBER  = os.getenv("USER_WHATSAPP_NUMBER", "")
USER_NAME    = os.getenv("USER_NAME", "Yashashri")
TWILIO_OK    = bool(TWILIO_SID and TWILIO_TOKEN)

twilio_client = None
if TWILIO_OK:
    try:
        from twilio.rest import Client as TwilioClient
        twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
        logger.info("✅ Twilio client initialised")
    except ImportError:
        logger.warning("twilio not installed — run: pip install twilio")
    except Exception as e:
        logger.error(f"Twilio init failed: {e}")
else:
    logger.warning("Twilio credentials not set — messages logged to console only")

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ─────────────────────────────────────────────────────────────────────────────
# SEND — synchronous, safe, always logs
# ─────────────────────────────────────────────────────────────────────────────
def send_whatsapp(to: str, body: str):
    """Send WhatsApp message. Falls back to console log if Twilio not set up."""
    if len(body) > 1550:
        body = body[:1520] + "\n\n…(truncated)"
    logger.info(f"[SEND] to={to[:20]} len={len(body)}")
    if twilio_client and to:
        try:
            msg = twilio_client.messages.create(from_=TWILIO_FROM, to=to, body=body)
            logger.info(f"[SENT] SID={msg.sid}")
        except Exception as e:
            logger.error(f"[TWILIO ERROR] {e}\n{traceback.format_exc()}")
    else:
        logger.info(f"\n{'='*50}\n[WHATSAPP MOCK → {to}]\n{body}\n{'='*50}")


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY — Twilio signature validation
# ─────────────────────────────────────────────────────────────────────────────
def _validate_twilio_signature(request_url: str, params: dict, signature: str) -> bool:
    """Verify request genuinely came from Twilio. Fails open in dev mode."""
    try:
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        if not auth_token or not signature:
            return True  # dev mode — no token set
        from twilio.request_validator import RequestValidator
        return RequestValidator(auth_token).validate(request_url, params, signature)
    except Exception:
        return True  # fail open — never block legitimate Twilio requests


# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOK — Twilio calls this on every incoming message
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    Body: str = Form(...),
    From: str = Form(...),
):
    # ── Twilio signature validation ───────────────────────────────────────────
    signature   = request.headers.get("X-Twilio-Signature", "")
    request_url = str(request.url)
    if request.headers.get("X-Forwarded-Proto") == "https":
        request_url = request_url.replace("http://", "https://")
    form_data = dict(await request.form())
    if not _validate_twilio_signature(request_url, form_data, signature):
        logger.warning(f"[WEBHOOK] BLOCKED — invalid Twilio signature from {request.client.host}")
        return PlainTextResponse("Forbidden", status_code=403)

    text = Body.strip()
    cmd  = text.lower().strip()
    logger.info(f"[WEBHOOK] from={From[:20]} msg='{text[:60]}'")

    if cmd in ("help", "hi", "hello", "start", "menu"):
        reply = (
            f"👋 *Endo Tracker* — Hi {USER_NAME}!\n\n"
            "Send your daily update naturally:\n\n"
            "*Example:*\n"
            "_Steps 7200, ate dal rice and salad,_\n"
            "_feeling 6/10, mild cramps lower abdomen,_\n"
            "_period day 2, ginger tea, took ibuprofen,_\n"
            "_30 min gentle yoga, slept 7 hrs_\n\n"
            "*Commands:*\n"
            "• *summary* — 7-day quick stats\n"
            "• *weekly* — full AI report\n"
            "• *help* — this menu\n\n"
            "💜 Everything stays private."
        )
        background_tasks.add_task(send_whatsapp, From, reply)
        return ""

    if cmd in ("summary", "stats", "report"):
        background_tasks.add_task(_task_summary, From)
        return ""

    if cmd in ("weekly", "weekly report", "recommend"):
        background_tasks.add_task(send_whatsapp, From,
            "🔄 Generating your weekly report… ~30 sec!")
        background_tasks.add_task(_task_weekly, From)
        return ""

    # Health log — send immediate ack then process
    background_tasks.add_task(send_whatsapp, From, "⏳ Processing your log…")
    background_tasks.add_task(_task_process_log, From, text)
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASKS — all synchronous (not async) so BackgroundTasks runs them
# ─────────────────────────────────────────────────────────────────────────────
def _task_process_log(sender: str, text: str):
    """Parse → save → nutrition → insight → reply. Fully wrapped in try/except."""
    logger.info(f"[TASK] _task_process_log start")
    try:
        from app.daily_log_db       import upsert_daily_log, get_logs
        from app.health_parser      import parse_health_message, build_confirmation
        from app.knowledge_engine   import estimate_nutrition, get_food_and_cycle_insight
        from app.cycle_intelligence import get_cycle_context

        # 1. Parse
        result = parse_health_message(text)
        data   = result["data"]
        data["raw_message"] = text
        logger.info(f"[TASK] parsed ok — pain={data.get('pain_score')} meals={data.get('meals')}")

        # 2. Save to DB
        db_result = upsert_daily_log(data)
        action    = db_result["action"]
        logger.info(f"[TASK] db saved — action={action}")

        # 2b. Log parse quality
        try:
            from app.daily_log_db import save_parse_log
            parse_source = result.get("error") or "llama_attempt1"
            if parse_source == "regex_fallback":
                source_label = "regex_fallback"
            elif parse_source == "llama_attempt2":
                source_label = "llama_attempt2"
            else:
                source_label = "llama_attempt1"
            save_parse_log(
                log_date=data.get("log_date", str(__import__("datetime").date.today())),
                raw_message=text,
                parse_source=source_label,
                data=data,
            )
        except Exception as e:
            logger.warning(f"[TASK] save_parse_log failed (non-fatal): {e}")

        # 3. Nutrition estimate
        nutrition = {}
        try:
            nutrition = estimate_nutrition(
                data.get("meals") or [],
                data.get("herbal_drinks") or [],
                text,
            )
            logger.info(f"[TASK] nutrition — calories={nutrition.get('calories')}")
            # Save nutrition directly to DB via dedicated UPDATE (not upsert)
            if nutrition.get("calories"):
                from app.daily_log_db import update_nutrition
                update_nutrition(
                    log_date=data.get("log_date", str(__import__("datetime").date.today())),
                    nutrition=nutrition,
                )
                logger.info(f"[TASK] nutrition saved to DB via direct UPDATE")
        except Exception as e:
            logger.warning(f"[TASK] nutrition failed (non-fatal): {e}")

        # 4. Confirmation message
        reply = build_confirmation(data, action, nutrition=nutrition)

        # 5. RAG insight — non-fatal if Ollama is down
        try:
            all_logs  = get_logs(days=120)
            cycle_ctx = get_cycle_context(all_logs)
            recent_7  = get_logs(days=7)

            insight = get_food_and_cycle_insight(
                today_data=data,
                logs=recent_7,
                cycle_day=cycle_ctx.get("cycle_day"),
                phase=cycle_ctx.get("phase_key"),
            )

            if insight:
                reply += "\n\n─────────────────\n🌿 *Today's insights:*\n" + insight

            if cycle_ctx.get("phase") and cycle_ctx.get("phase") != "unknown":
                em = cycle_ctx.get("phase_emoji", "🗓️")
                cd = cycle_ctx.get("cycle_day", "?")
                reply += f"\n\n{em} _{cycle_ctx['phase']} — day {cd}_"

        except Exception as e:
            logger.warning(f"[TASK] insight failed (non-fatal): {e}")

        # 6. Save insight to log table
        try:
            from app.daily_log_db import save_insight
            save_insight(
                log_date=data.get("log_date", str(__import__("datetime").date.today())),
                user_message=text,
                ai_reply=reply,
                insight_type="daily",
            )
        except Exception as e:
            logger.warning(f"[TASK] save_insight failed (non-fatal): {e}")

        logger.info(f"[TASK] sending reply to {sender[:20]} len={len(reply)}")
        send_whatsapp(sender, reply)

    except Exception as e:
        logger.error(f"[TASK] _task_process_log FAILED:\n{traceback.format_exc()}")
        send_whatsapp(sender,
            "✅ Heard you! But something went wrong saving your log.\n"
            f"Error: {str(e)[:100]}\n\n"
            "Try again or reply *help*."
        )


def _task_summary(sender: str):
    logger.info("[TASK] _task_summary start")
    try:
        from app.daily_log_db          import get_logs
        from app.recommendation_engine import build_quick_summary
        logs  = get_logs(days=7)
        reply = build_quick_summary(logs)
        send_whatsapp(sender, reply)
    except Exception as e:
        logger.error(f"[TASK] summary failed: {e}\n{traceback.format_exc()}")
        send_whatsapp(sender, f"Couldn't generate summary. Error: {str(e)[:80]}")


def _task_weekly(sender: str):
    logger.info("[TASK] _task_weekly start")
    try:
        from app.daily_log_db          import get_logs, get_weekly_summary
        from app.recommendation_engine import generate_weekly_report

        this_week = get_weekly_summary(0)
        last_week = get_weekly_summary(1)
        logs      = get_logs(days=7)

        if this_week.get("days_logged", 0) == 0:
            send_whatsapp(sender,
                "📊 No logs this week yet!\n\n"
                "Log daily to unlock your personalised weekly report 💜\n"
                "Reply *help* to see how."
            )
            return

        message = generate_weekly_report(this_week, last_week, logs=logs)
        try:
            from app.daily_log_db import save_insight
            import datetime
            save_insight(str(datetime.date.today()), "weekly report request", message, "weekly")
        except Exception:
            pass
        send_whatsapp(sender, message)
    except Exception as e:
        logger.error(f"[TASK] weekly failed: {e}\n{traceback.format_exc()}")
        send_whatsapp(sender, f"Couldn't generate weekly report. Error: {str(e)[:80]}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST ENDPOINTS — no Twilio needed
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/test-log")
async def test_log(body: dict):
    """
    Full pipeline test without Twilio.
    POST {"message": "Steps 7000, ate dal sabji, pain 6, period day 2, 30 min yoga"}
    """
    msg = body.get("message", "")
    if not msg:
        raise HTTPException(400, "message required")

    from app.health_parser    import parse_health_message, build_confirmation
    from app.daily_log_db     import upsert_daily_log, get_logs
    from app.knowledge_engine import estimate_nutrition, get_food_and_cycle_insight
    from app.cycle_intelligence import get_cycle_context

    result    = parse_health_message(msg)
    data      = result["data"]
    data["raw_message"] = msg
    db_result = upsert_daily_log(data)
    nutrition = estimate_nutrition(data.get("meals") or [], data.get("herbal_drinks") or [], msg)
    all_logs  = get_logs(days=120)
    cycle_ctx = get_cycle_context(all_logs)
    recent_7  = get_logs(days=7)
    insight   = get_food_and_cycle_insight(
        today_data=data, logs=recent_7,
        cycle_day=cycle_ctx.get("cycle_day"),
        phase=cycle_ctx.get("phase_key"),
    )

    confirmation = build_confirmation(data, db_result["action"], nutrition=nutrition)
    if insight:
        confirmation += f"\n\n─────────────────\n🌿 *Today's insights:*\n{insight}"

    return {
        "parsed":     data,
        "db_action":  db_result["action"],
        "nutrition":  nutrition,
        "cycle":      cycle_ctx,
        "reply":      confirmation,
    }


@router.post("/test-parse")
async def test_parse(body: dict):
    """Just test NLP parsing. POST {"message": "..."}"""
    from app.health_parser import parse_health_message
    msg = body.get("message", "")
    if not msg:
        raise HTTPException(400, "message required")
    return parse_health_message(msg)


@router.post("/send-weekly")
async def trigger_weekly(background_tasks: BackgroundTasks):
    """Manually trigger weekly report → USER_WHATSAPP_NUMBER."""
    if not USER_NUMBER:
        raise HTTPException(400, "USER_WHATSAPP_NUMBER not set in .env")
    background_tasks.add_task(_task_weekly, USER_NUMBER)
    return {"status": "started", "sending_to": USER_NUMBER}


@router.get("/status")
async def whatsapp_status():
    return {
        "twilio_configured": TWILIO_OK,
        "twilio_client_ok":  twilio_client is not None,
        "user_number_set":   bool(USER_NUMBER),
        "from_number":       TWILIO_FROM,
        "user_number_masked": USER_NUMBER[:8] + "…" if USER_NUMBER else "not set",
        "mode":              "live" if twilio_client else "console_mock",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SUNDAY SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────
_scheduler = None

def start_weekly_scheduler():
    global _scheduler
    if _scheduler:
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _task_weekly, trigger="cron",
            day_of_week="sun", hour=19, minute=0,
            args=[USER_NUMBER] if USER_NUMBER else [],
            id="weekly_whatsapp_report",
        )
        _scheduler.start()
        logger.info("✅ Weekly scheduler running — Sundays 7pm")
    except ImportError:
        logger.warning("apscheduler not installed — run: pip install apscheduler")
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")


@router.post("/debug-send")
async def debug_send(body: dict):
    """
    Test Twilio send directly.
    POST {"message": "test", "to": "whatsapp:+91XXXXXXXXXX"}
    Or omit 'to' to use USER_WHATSAPP_NUMBER from .env
    """
    msg = body.get("message", "🔧 Test message from Endo Tracker debug endpoint")
    to  = body.get("to") or USER_NUMBER
    if not to:
        raise HTTPException(400, "No 'to' number and USER_WHATSAPP_NUMBER not set in .env")

    if not twilio_client:
        return {
            "status": "no_twilio",
            "reason": "Twilio not configured — check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env",
            "twilio_ok": TWILIO_OK,
        }
    try:
        sent = twilio_client.messages.create(from_=TWILIO_FROM, to=to, body=msg)
        return {"status": "sent", "sid": sent.sid, "to": to, "body": msg}
    except Exception as e:
        return {"status": "failed", "error": str(e), "to": to}


@router.get("/debug-env")
async def debug_env():
    """Check all env vars are loaded correctly (masks secrets)."""
    return {
        "TWILIO_SID_set":    bool(TWILIO_SID) and TWILIO_SID[:4] + "…",
        "TWILIO_TOKEN_set":  bool(TWILIO_TOKEN),
        "TWILIO_FROM":       TWILIO_FROM,
        "USER_NUMBER":       USER_NUMBER[:12] + "…" if USER_NUMBER else "NOT SET ❌",
        "USER_NAME":         USER_NAME,
        "twilio_client_ok":  twilio_client is not None,
        "TWILIO_OK":         TWILIO_OK,
    }