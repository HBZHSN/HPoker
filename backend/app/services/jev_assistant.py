"""TypeSafe Jev decisions for the current player's visible poker state."""

import json
import math
import time

import httpx

from backend.app.database import SQLiteDatabase


API_URL = "https://api.typesafe.ai/v1/systemone"


class JevAssistant:
    def __init__(self, database_path=None):
        self.database = SQLiteDatabase(database_path)

    def settings(self):
        with self.database.connection() as db:
            return dict(db.execute(
                "SELECT api_key, uses_per_coin, configured_at, recipient_user_id FROM jev_settings WHERE singleton_id = 1"
            ).fetchone())

    def public_settings(self):
        config = self.settings()
        return {
            "has_key": bool(config["api_key"]),
            "uses_per_coin": config["uses_per_coin"],
            "recipient_user_id": config["recipient_user_id"],
        }

    def update_settings(self, *, api_key, uses_per_coin, admin_id):
        if type(uses_per_coin) is not int or not 0 <= uses_per_coin <= 1000000:
            raise ValueError("每 H币调用次数须为 0 至 1000000 的整数")
        if api_key is not None and (not isinstance(api_key, str) or len(api_key) > 512):
            raise ValueError("API key 无效")
        with self.database.connection(write=True) as db:
            current = db.execute(
                "SELECT uses_per_coin, recipient_user_id FROM jev_settings WHERE singleton_id = 1"
            ).fetchone()
            configured_at = time.time() if (current[0], current[1]) != (uses_per_coin, admin_id) else None
            if api_key is None:
                db.execute(
                    "UPDATE jev_settings SET uses_per_coin = ?, recipient_user_id = ?, "
                    "configured_at = COALESCE(?, configured_at) WHERE singleton_id = 1",
                    (uses_per_coin, admin_id, configured_at),
                )
            else:
                db.execute(
                    "UPDATE jev_settings SET api_key = ?, uses_per_coin = ?, recipient_user_id = ?, "
                    "configured_at = COALESCE(?, configured_at) WHERE singleton_id = 1",
                    (api_key.strip(), uses_per_coin, admin_id, configured_at),
                )
        return self.public_settings()

    def charge_cents(self, user_id, settings):
        uses_per_coin = settings["uses_per_coin"]
        if uses_per_coin == 0:
            return 0
        with self.database.connection() as db:
            used = db.execute(
                "SELECT COUNT(*) FROM jev_decisions WHERE user_id = ? AND created_at >= ?",
                (user_id, settings["configured_at"]),
            ).fetchone()[0]
        # Round cumulative cost up to cents: 1 H币 / 1000 次 charges on uses 1, 11, 21...
        return (100 * (used + 1) + uses_per_coin - 1) // uses_per_coin - (100 * used + uses_per_coin - 1) // uses_per_coin

    def cached(self, decision_id, user_id):
        with self.database.connection() as db:
            row = db.execute(
                "SELECT result_json FROM jev_decisions WHERE decision_id = ? AND user_id = ?",
                (decision_id, user_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, decision_id, user_id, result):
        with self.database.connection(write=True) as db:
            db.execute(
                "INSERT OR IGNORE INTO jev_decisions(decision_id, user_id, result_json, created_at) VALUES (?, ?, ?, ?)",
                (decision_id, user_id, json.dumps(result), time.time()),
            )

    async def recommend(self, *, api_key, state, legal):
        options = {"fold": "弃牌并放弃本手"}
        if legal.can_check or legal.can_call:
            options["call"] = "过牌（无需跟注）" if legal.can_check else "支付跟注额继续游戏"
        if legal.can_bet or legal.can_raise:
            options["raise"] = "下注或加注，需考虑筹码、底池、位置和对手行动"
        payload = {
            "model": "jev-latest",
            "state": state,
            "questions": {"action": {
                "type": "choice",
                "instructions": "根据德州扑克可见信息，选择当前玩家最合理的行动。对手 public_stats 是公开历史数据，比例为 0 到 100，win_rate 是历史净赢手数比例而非当前手牌胜率，null 表示无样本。仅使用给出的手牌和公共信息；不要假设对手暗牌。返回各合法选项的推荐概率。",
                "criteria": options,
            }},
        }
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            response = await client.post(API_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"})
            response.raise_for_status()
            data = response.json()
            answer = data["answers"]["action"]
        probabilities = answer["probabilities"]
        if answer.get("type") != "choice" or set(probabilities) != set(options) or any(
            not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or value > 1
            for value in probabilities.values()
        ) or not 0.99 <= sum(probabilities.values()) <= 1.01 or answer.get("choice") not in options:
            raise ValueError("Jev 返回的行动概率无效")
        confidence = answer.get("confidence")
        if confidence is not None and (
            type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1
        ):
            raise ValueError("Jev 返回的置信度无效")
        return {
            "recommendation": answer["choice"],
            "probabilities": {option: probabilities.get(option, 0) for option in ("fold", "call", "raise")},
            "confidence": confidence,
            "model": data.get("model", "jev-latest"),
            "request": payload,
        }


jev_assistant = JevAssistant()
