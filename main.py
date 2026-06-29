"""
jarvis-cloud/main.py — JARVIS Cloud Edition
"""

from __future__ import annotations
import threading

from server import start_server
import asyncio
import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google import genai
from google.genai import types

from actions.web_search  import web_search
from actions.weather     import get_weather
from actions.reminder    import reminder, set_reminder_callback
from actions.code_helper import code_helper
from actions.gmail       import gmail_action

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR    = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "config" / "prompt.txt"
MODEL       = "gemini-2.5-flash"

def _cfg() -> dict:
    return {
        "gemini_api_key":      os.environ["GEMINI_API_KEY"],
        "telegram_bot_token":  os.environ["TELEGRAM_BOT_TOKEN"],
        "telegram_chat_id":    os.environ.get("TELEGRAM_CHAT_ID", ""),
        "openweather_api_key": os.environ.get("OPENWEATHER_API_KEY", ""),
    }

def _prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "Você é JARVIS, assistente pessoal de IA. "
            "Seja formal, direto e chame o usuário de 'senhor'. "
            "Responda em português por padrão. "
            "Nunca simule resultados — use sempre as ferramentas disponíveis."
        )

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "web_search",
        "description": "Pesquisa na internet. Use para notícias, fatos atuais, preços, eventos. Também use para buscar e resumir o conteúdo de URLs específicas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Termo de busca ou URL"},
                "count": {"type": "INTEGER", "description": "Número de resultados (padrão: 5)"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Retorna o clima atual de uma cidade.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "Nome da cidade"},
            },
            "required": ["city"]
        }
    },
    {
        "name": "reminder",
        "description": "Define um lembrete enviado pelo Telegram após o tempo especificado.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "Texto do lembrete"},
                "minutes": {"type": "NUMBER", "description": "Minutos até o lembrete"},
                "hours":   {"type": "NUMBER", "description": "Horas até o lembrete"},
            },
            "required": ["message"]
        }
    },
    {
        "name": "gmail",
        "description": "Gerencia emails: ler, enviar, responder, resumir, sugerir resposta, organizar por categoria.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":     {"type": "STRING",  "description": "read | send | reply | detail | mark_read | summarize | suggest_reply | categorize"},
                "count":      {"type": "INTEGER", "description": "Quantidade de emails (padrão: 5)"},
                "query":      {"type": "STRING",  "description": "Filtro Gmail (padrão: is:unread)"},
                "to":         {"type": "STRING",  "description": "Destinatário (send)"},
                "subject":    {"type": "STRING",  "description": "Assunto (send)"},
                "body":       {"type": "STRING",  "description": "Corpo do email (send/reply)"},
                "message_id": {"type": "STRING",  "description": "ID da mensagem (reply/detail/mark_read/summarize/suggest_reply)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Ajuda com código: escrever, explicar, corrigir, refatorar, revisar, gerar testes unitários, comparar versões.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task":     {"type": "STRING", "description": "Descrição da tarefa (refactor | review | test | compare | write | explain | fix)"},
                "language": {"type": "STRING", "description": "Linguagem de programação (padrão: Python)"},
                "code":     {"type": "STRING", "description": "Código existente (opcional)"},
                "code2":    {"type": "STRING", "description": "Segunda versão do código para comparação (opcional)"},
            },
            "required": ["task"]
        }
    },
    {
        "name": "get_datetime",
        "description": "Retorna a data e hora atual.",
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
]

# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

_histories: dict[str, list[dict]] = {}

def _get_history(chat_id: str) -> list[dict]:
    if chat_id not in _histories:
        _histories[chat_id] = []
    return _histories[chat_id]

def _add_to_history(chat_id: str, role: str, text: str) -> None:
    h = _get_history(chat_id)
    h.append({"role": role, "parts": [{"text": text}]})
    if len(h) > 30:
        _histories[chat_id] = h[-30:]

def _clear_history(chat_id: str) -> None:
    _histories[chat_id] = []

# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def _execute_tool(name: str, args: dict) -> str:
    print(f"[JARVIS] 🔧 {name} {args}")
    try:
        if name == "web_search":
            return web_search(parameters=args)
        elif name == "get_weather":
            return get_weather(parameters=args)
        elif name == "reminder":
            return reminder(parameters=args)
        elif name == "gmail":
            return gmail_action(parameters=args)
        elif name == "code_helper":
            return code_helper(parameters=args)
        elif name == "get_datetime":
            now = datetime.now()
            return f"Data e hora atual: {now.strftime('%d/%m/%Y %H:%M:%S')}"
        else:
            return f"Ferramenta desconhecida: {name}"
    except Exception as e:
        return f"Erro na ferramenta {name}: {e}"

# ---------------------------------------------------------------------------
# Gemini — texto
# ---------------------------------------------------------------------------

def process_message(chat_id: str, user_text: str) -> str:
    cfg    = _cfg()
    client = genai.Client(api_key=cfg["gemini_api_key"])

    _add_to_history(chat_id, "user", user_text)

    contents = [
        types.Content(
            role=turn["role"],
            parts=[types.Part(text=p["text"]) for p in turn["parts"]]
        )
        for turn in _get_history(chat_id)
    ]

    tool_config = types.GenerateContentConfig(
        system_instruction=_prompt(),
        tools=[{"function_declarations": TOOLS}],
    )

    for _ in range(5):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=contents, config=tool_config,
            )
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                return "Desculpe senhor, o limite de requisições foi atingido. Tente novamente mais tarde."
            raise

        candidate = response.candidates[0] if response.candidates else None
        if not candidate:
            break

        tool_calls = [
            p for p in candidate.content.parts
            if hasattr(p, "function_call") and p.function_call
        ]

        if not tool_calls:
            text = response.text or ""
            if text:
                _add_to_history(chat_id, "model", text)
            return text

        contents.append(candidate.content)
        fn_responses = []
        for part in tool_calls:
            fc     = part.function_call
            result = _execute_tool(fc.name, dict(fc.args))
            fn_responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response={"result": result}
                    )
                )
            )
        contents.append(types.Content(role="user", parts=fn_responses))

    return "Desculpe, senhor. Não consegui processar sua solicitação."

# ---------------------------------------------------------------------------
# Gemini — imagem
# ---------------------------------------------------------------------------

def process_image(chat_id: str, image_bytes: bytes, mime_type: str, caption: str = "") -> str:
    cfg    = _cfg()
    client = genai.Client(api_key=cfg["gemini_api_key"])
    prompt = caption if caption else "Analise esta imagem detalhadamente. Se houver texto, extraia-o. Descreva tudo que vê."

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(parts=[
                    types.Part(inline_data=types.Blob(mime_type=mime_type, data=image_bytes)),
                    types.Part(text=prompt),
                ])
            ],
            config=types.GenerateContentConfig(system_instruction=_prompt()),
        )
        reply = response.text or "Não consegui analisar a imagem, senhor."
        _add_to_history(chat_id, "user", f"[Imagem enviada] {prompt}")
        _add_to_history(chat_id, "model", reply)
        return reply
    except Exception as e:
        return f"Erro ao processar imagem: {e}"

# ---------------------------------------------------------------------------
# Gemini — PDF
# ---------------------------------------------------------------------------

def process_pdf(chat_id: str, pdf_bytes: bytes, caption: str = "") -> str:
    cfg    = _cfg()
    client = genai.Client(api_key=cfg["gemini_api_key"])
    prompt = caption if caption else "Resuma este documento de forma clara e objetiva. Destaque os pontos mais importantes."

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(parts=[
                    types.Part(inline_data=types.Blob(mime_type="application/pdf", data=pdf_bytes)),
                    types.Part(text=prompt),
                ])
            ],
            config=types.GenerateContentConfig(system_instruction=_prompt()),
        )
        reply = response.text or "Não consegui analisar o PDF, senhor."
        _add_to_history(chat_id, "user", f"[PDF enviado] {prompt}")
        _add_to_history(chat_id, "model", reply)
        return reply
    except Exception as e:
        return f"Erro ao processar PDF: {e}"

# ---------------------------------------------------------------------------
# Transcrição de voz
# ---------------------------------------------------------------------------

def transcribe_audio(audio_bytes: bytes) -> str:
    try:
        cfg    = _cfg()
        client = genai.Client(api_key=cfg["gemini_api_key"])
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(parts=[
                    types.Part(inline_data=types.Blob(mime_type="audio/ogg", data=audio_bytes)),
                    types.Part(text="Transcreva exatamente o que foi dito neste áudio. Retorne apenas a transcrição, sem comentários."),
                ])
            ],
        )
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"[Voice] Erro na transcrição: {e}")
        return ""

# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------

_bot_ref: Optional[Any] = None
_owner_chat_id: Optional[str] = None

def _send_to_telegram(text: str) -> None:
    if not _bot_ref or not _owner_chat_id:
        return
    async def _send() -> None:
        await _bot_ref.send_message(chat_id=_owner_chat_id, text=text)
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_send())
        loop.close()
    except Exception as e:
        print(f"[Reminder] Erro ao enviar: {e}")

def run_bot() -> None:
    threading.Thread(target=start_server, daemon=True).start()
    global _bot_ref, _owner_chat_id

    try:
        from telegram import Update
        from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
    except ImportError:
        print("❌ python-telegram-bot não instalado.")
        sys.exit(1)

    token = _cfg()["telegram_bot_token"]
    _owner_chat_id = _cfg().get("telegram_chat_id") or None

    set_reminder_callback(_send_to_telegram)

    # --- Comandos ---

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "🤖 *JARVIS Cloud Online*\n\n"
            "Estou pronto para auxiliá-lo, senhor.\n\n"
            "Use /help para ver os comandos disponíveis.",
            parse_mode="Markdown"
        )

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "📋 *Comandos disponíveis:*\n\n"
            "/start — Iniciar o bot\n"
            "/help — Esta mensagem\n"
            "/clear — Limpar histórico da conversa\n\n"
            "📎 *Também aceito:*\n"
            "• Mensagens de texto\n"
            "• Imagens (com ou sem legenda)\n"
            "• Áudios de voz\n"
            "• Documentos PDF\n"
            "• Links para resumir\n\n"
            "🔧 *Ferramentas disponíveis:*\n"
            "• Pesquisa web\n"
            "• Clima\n"
            "• Gmail\n"
            "• Lembretes\n"
            "• Ajuda com código",
            parse_mode="Markdown"
        )

    async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = str(update.effective_chat.id)
        _clear_history(chat_id)
        await update.message.reply_text("Histórico limpo, senhor. Podemos começar do zero.")

    # --- Mensagens ---

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        global _owner_chat_id
        if not update.message or not update.message.text:
            return
        chat_id = str(update.effective_chat.id)
        if not _owner_chat_id:
            _owner_chat_id = chat_id
        user_text = update.message.text
        sender    = update.message.from_user.first_name if update.message.from_user else "?"
        print(f"[Telegram] 📨 {sender}: {user_text!r}")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        loop  = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, process_message, chat_id, user_text)
        if reply:
            for i in range(0, len(reply), 4000):
                await update.message.reply_text(reply[i:i+4000])

    async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        global _owner_chat_id
        if not update.message:
            return
        chat_id = str(update.effective_chat.id)
        if not _owner_chat_id:
            _owner_chat_id = chat_id
        caption = update.message.caption or ""
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        photo = update.message.photo[-1]
        file  = await context.bot.get_file(photo.file_id)
        buf   = io.BytesIO()
        await file.download_to_memory(buf)
        print(f"[Telegram] 🖼️ Imagem recebida ({len(buf.getvalue())} bytes)")
        loop  = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, process_image, chat_id, buf.getvalue(), "image/jpeg", caption)
        if reply:
            for i in range(0, len(reply), 4000):
                await update.message.reply_text(reply[i:i+4000])

    async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        global _owner_chat_id
        if not update.message:
            return
        chat_id = str(update.effective_chat.id)
        if not _owner_chat_id:
            _owner_chat_id = chat_id
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        file = await context.bot.get_file(update.message.voice.file_id)
        buf  = io.BytesIO()
        await file.download_to_memory(buf)
        print(f"[Telegram] 🎤 Áudio recebido ({len(buf.getvalue())} bytes)")
        loop        = asyncio.get_running_loop()
        transcribed = await loop.run_in_executor(None, transcribe_audio, buf.getvalue())
        if not transcribed:
            await update.message.reply_text("Não consegui entender o áudio, senhor. Poderia repetir?")
            return
        reply = await loop.run_in_executor(None, process_message, chat_id, transcribed)
        if reply:
            for i in range(0, len(reply), 4000):
                await update.message.reply_text(reply[i:i+4000])

    async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        global _owner_chat_id
        if not update.message or not update.message.document:
            return
        chat_id = str(update.effective_chat.id)
        if not _owner_chat_id:
            _owner_chat_id = chat_id
        doc     = update.message.document
        caption = update.message.caption or ""
        if not doc.mime_type or "pdf" not in doc.mime_type:
            await update.message.reply_text("Por enquanto só consigo analisar arquivos PDF, senhor.")
            return
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        file = await context.bot.get_file(doc.file_id)
        buf  = io.BytesIO()
        await file.download_to_memory(buf)
        print(f"[Telegram] 📄 PDF recebido ({buf.tell()} bytes)")
        loop  = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, process_pdf, chat_id, buf.getvalue(), caption)
        if reply:
            for i in range(0, len(reply), 4000):
                await update.message.reply_text(reply[i:i+4000])

    app = Application.builder().token(token).build()
    _bot_ref = app.bot

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO,        handle_image))
    app.add_handler(MessageHandler(filters.VOICE,        handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("[JARVIS Cloud] 🟢 Bot iniciado com suporte a texto, imagem, voz e PDF.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    run_bot()