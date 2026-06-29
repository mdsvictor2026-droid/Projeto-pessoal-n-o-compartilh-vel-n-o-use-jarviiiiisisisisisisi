"""actions/reminder.py — Lembretes simples com threading"""
from __future__ import annotations
import threading, time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

_send_callback: Optional[Callable[[str], None]] = None

def set_reminder_callback(cb: Callable[[str], None]) -> None:
    global _send_callback
    _send_callback = cb

def reminder(parameters: dict | None = None, **_: Any) -> str:
    params  = parameters or {}
    message = params.get("message", "Lembrete!").strip()
    minutes = float(params.get("minutes", 0))
    hours   = float(params.get("hours", 0))
    delay   = minutes * 60 + hours * 3600

    if delay <= 0:
        return "Preciso de um tempo válido para o lembrete (minutes ou hours), senhor."

    due = datetime.now() + timedelta(seconds=delay)
    due_str = due.strftime("%H:%M")

    def _fire() -> None:
        time.sleep(delay)
        text = f"⏰ Lembrete: {message}"
        print(f"[Reminder] {text}")
        if _send_callback:
            _send_callback(text)

    threading.Thread(target=_fire, daemon=True).start()
    return f"Lembrete definido para {due_str}: '{message}'"
