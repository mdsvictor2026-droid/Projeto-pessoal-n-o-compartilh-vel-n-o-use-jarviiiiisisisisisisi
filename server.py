"""
server.py — Servidor HTTP para o JARVIS Mini App
Roda junto com o bot Telegram no mesmo processo.

Adicione no seu main.py:
    from server import start_server
    threading.Thread(target=start_server, daemon=True).start()

Variável de ambiente necessária no Railway:
    PORT (Railway define automaticamente)
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Importa a função de processamento do seu main.py
# (o server.py fica na mesma pasta que main.py)
from main import process_message

app = FastAPI()

BASE_DIR   = Path(__file__).resolve().parent
MINIAPP_DIR = BASE_DIR / "miniapp"


# ── Serve o index.html do Mini App ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
@app.get("/miniapp", response_class=HTMLResponse)
async def miniapp():
    html = (MINIAPP_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


# ── Endpoint de chat (chamado pelo Mini App via fetch) ────────────────────────

@app.post("/miniapp/chat")
async def miniapp_chat(request: Request):
    try:
        body    = await request.json()
        chat_id = str(body.get("chat_id", "miniapp"))
        text    = str(body.get("text", "")).strip()

        if not text:
            return JSONResponse({"reply": "Preciso de uma mensagem, senhor."})

        # Roda o processamento em thread separada (é blocante)
        loop  = __import__("asyncio").get_event_loop()
        reply = await loop.run_in_executor(None, process_message, chat_id, text)

        return JSONResponse({"reply": reply or "Sem resposta."})

    except Exception as e:
        print(f"[Server] ❌ Erro no /miniapp/chat: {e}")
        return JSONResponse({"reply": f"Erro interno: {e}"}, status_code=500)


# ── Inicia o servidor ─────────────────────────────────────────────────────────

def start_server():
    port = int(os.environ.get("PORT", 8080))
    print(f"[Server] 🌐 Mini App rodando em http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")