# webhook.py — Нейро-Студия v11
# Принимает колбэки Platega: разовые платежи (CONFIRMED/CANCELED) и подписки (ACTIVE/PAST_DUE/CANCELLED/FAILED)
# Запуск: python webhook.py
import os, time, sqlite3, hmac, logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("webhook")
app = Flask(__name__)

DB = os.path.join(os.getenv("DATA_DIR", "/app/data"), "media_bot.db")
PLATEGA_ID     = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET = os.getenv("PLATEGA_SECRET_KEY", "")

PACKAGE_MAP = {
    "img_10":("image",10), "img_25":("image",25), "img_50":("image",50), "img_100":("image",100),
    "aud_10":("audio",10), "aud_25":("audio",25),
    "vid_5":("video",5), "vid_15":("video",15),
    "tts_10":("tts",10),
    "stt_10":("stt",10), "stt_25":("stt",25),
    "edit_10":("edit",10),
    "anim_5":("animate",5),
    "up_10":("upscale",10),
}

SUB_TARIFFS = {
    "start": {"title":"Старт",  "limit": int(os.getenv("SUB_START_LIMIT","30")), "days":30},
    "pro":   {"title":"Про",    "limit": int(os.getenv("SUB_PRO_LIMIT","70")),   "days":30},
    "max":   {"title":"Максимум","limit": int(os.getenv("SUB_MAX_LIMIT","130")),  "days":30},
}

BAL_FIELD = {"image":"balance_img","audio":"balance_aud","video":"balance_vid","tts":"balance_tts",
             "stt":"balance_stt","edit":"balance_edit","animate":"balance_anim","upscale":"balance_up"}

def safe_eq(a, b):
    return hmac.compare_digest(str(a or ""), str(b or ""))

def get_conn():
    c = sqlite3.connect(DB, check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def upd_user(cur, uid, **kw):
    if not kw: return
    cols = ", ".join(f"{k}=?" for k in kw)
    cur.execute(f"UPDATE users SET {cols} WHERE user_id=?", (*kw.values(), uid))

@app.route("/platega/webhook", methods=["POST"])
def hook():
    # 1. проверка подписи
    if not safe_eq(request.headers.get("X-MerchantId"), PLATEGA_ID):
        return jsonify({"ok": False}), 403
    if not safe_eq(request.headers.get("X-Secret"), PLATEGA_SECRET):
        return jsonify({"ok": False}), 403

    data = request.get_json(silent=True) or {}
    tx_id = data.get("id")                 # для платежа — id платежа, для подписки — id подписки [citation:10]
    status = data.get("status")
    payload = data.get("payload", "")
    amount = data.get("amount")

    if not tx_id:
        return jsonify({"ok": False, "err": "no id"}), 400

    cc = get_conn(); cur = cc.cursor()

    # 2. Идемпотентность: если уже CONFIRMED — выходим
    cur.execute("SELECT status FROM payments WHERE platega_id=?", (tx_id,))
    row = cur.fetchone()
    if row and row[0] == "CONFIRMED":
        cc.close()
        return jsonify({"ok": True, "already": True})

    # 3. Определяем: подписка или разовый платёж
    # У подписки payload = "{uid}_sub_{code}_{ts}"
    # У разового = "{uid}_{pid}_{ts}"
    parts = payload.split("_") if payload else []
    is_sub = len(parts) >= 3 and parts[1] == "sub"

    if is_sub:
        # ---- Подписка ----
        if not payload:
            cc.close(); return jsonify({"ok": False, "err": "no payload"}), 400
        try:
            uid = int(parts[0])
            code = parts[2]
        except Exception:
            cc.close(); return jsonify({"ok": False, "err": "bad payload"}), 400

        # Статусы подписки: PENDING, ACTIVE, PAST_DUE, CANCELLED, FAILED [citation:8]
        if status == "ACTIVE":
            t = SUB_TARIFFS.get(code, {"days":30})
            until = time.time() + t["days"] * 86400
            # Активируем подписку
            upd_user(cur, uid, sub_plan=code, sub_until=until, sub_used=0,
                     sub_auto=1, sub_notified=0)
            cur.execute("UPDATE payments SET status='CONFIRMED' WHERE platega_id=?", (tx_id,))
            cur.execute("INSERT INTO logs(user_id,action,details,ts) VALUES(?,?,?,?)",
                        (uid, "sub_activated", f"{code} до {int(until)}", time.time()))
            cc.commit(); cc.close()
            log.info(f"SUB ACTIVE uid={uid} {code}")
            return jsonify({"ok": True})

        elif status in ("CANCELLED", "FAILED"):
            # Снимаем подписку
            upd_user(cur, uid, sub_plan="", sub_until=0, sub_used=0, sub_auto=0)
            cur.execute("UPDATE payments SET status=? WHERE platega_id=?", (status, tx_id))
            cur.execute("INSERT INTO logs(user_id,action,details,ts) VALUES(?,?,?,?)",
                        (uid, "sub_deactivated", f"{status} {code}", time.time()))
            cc.commit(); cc.close()
            log.info(f"SUB {status} uid={uid} {code}")
            return jsonify({"ok": True})

        elif status == "PAST_DUE":
            # Списание не прошло, но подписка ещё жива — просто логируем
            cur.execute("INSERT INTO logs(user_id,action,details,ts) VALUES(?,?,?,?)",
                        (uid, "sub_past_due", f"{code}", time.time()))
            cc.commit(); cc.close()
            log.warning(f"SUB PAST_DUE uid={uid} {code}")
            return jsonify({"ok": True})

        # PENDING или неизвестный — игнорируем
        cc.close()
        return jsonify({"ok": True})

    # ---- Разовый платёж (пакет) ----
    if not parts or len(parts) < 2:
        cc.close(); return jsonify({"ok": False, "err": "bad payload"}), 400
    try:
        uid = int(parts[0])
        pid = parts[1]
    except Exception:
        cc.close(); return jsonify({"ok": False, "err": "bad uid/pid"}), 400

    if status != "CONFIRMED":
        # CANCELED / CHARGEBACKED / PARTIALLY_REFUNDED / DISPUTED — просто обновляем статус
        cur.execute("UPDATE payments SET status=? WHERE platega_id=?", (status, tx_id))
        cc.commit(); cc.close()
        log.info(f"PAYMENT {status} tx={tx_id}")
        return jsonify({"ok": True})

    # CONFIRMED — выдаём пакет
    p = PACKAGE_MAP.get(pid)
    if not p:
        cc.close(); log.error(f"unknown pid {pid}")
        return jsonify({"ok": False, "err": "unknown pid"}), 400

    # Сверка суммы (защита от подмены)
    cur.execute("SELECT amount FROM payments WHERE platega_id=?", (tx_id,))
    amt_row = cur.fetchone()
    if amt_row and amount is not None:
        try:
            if int(float(amount)) != int(amt_row[0]):
                log.warning(f"amount mismatch tx={tx_id}: got {amount}, expected {amt_row[0]}")
                cc.close()
                return jsonify({"ok": False, "err": "amount mismatch"}), 400
        except Exception:
            pass

    m_type, count = p
    col = BAL_FIELD[m_type]
    cur.execute(f"UPDATE users SET {col}={col}+?, q_bought=1 WHERE user_id=?", (count, uid))
    cur.execute("UPDATE payments SET status='CONFIRMED' WHERE platega_id=?", (tx_id,))
    cur.execute("INSERT INTO logs(user_id,action,details,ts) VALUES(?,?,?,?)",
                (uid, "payment_confirmed", f"{pid}: +{count} {m_type}", time.time()))
    cc.commit(); cc.close()
    log.info(f"PACKAGE CONFIRMED uid={uid} {pid} +{count} {m_type}")
    return jsonify({"ok": True})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "ts": time.time()})


if __name__ == "__main__":
    log.info(f"🚀 Webhook на порту {os.getenv('WEBHOOK_PORT', '8080')}")
    app.run(host="0.0.0.0", port=int(os.getenv("WEBHOOK_PORT", "8080")))