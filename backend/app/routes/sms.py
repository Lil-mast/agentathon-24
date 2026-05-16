from flask import Blueprint, current_app, request

from app.services.digest import build_reply_for_question
from app.services.sms import send_sms


sms_bp = Blueprint("sms", __name__)


@sms_bp.post("/api/sms/inbound")
def inbound_sms():
    payload = request.get_json(silent=True) or {}
    from_phone = (payload.get("from") or payload.get("phone") or "").strip()
    text = (payload.get("text") or payload.get("message") or "").strip()

    if not from_phone or not text:
        return {"error": "from/phone and text/message are required"}, 400

    reply = build_reply_for_question(current_app.config, phone=from_phone, question=text)
    sms_result = send_sms(current_app.config, to=from_phone, message=reply)
    return {"status": "ok", "reply": reply, "sms": sms_result}, 200
