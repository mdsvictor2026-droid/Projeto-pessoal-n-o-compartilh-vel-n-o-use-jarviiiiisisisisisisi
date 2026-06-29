"""actions/gmail.py — Gmail (mesma versão do Jarvis local)"""
from __future__ import annotations
import base64, json, sys
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

def _base_dir() -> Path:
    return Path(__file__).resolve().parent.parent

CREDS_PATH = _base_dir() / "config" / "credentials_gmail.json"
TOKEN_PATH = _base_dir() / "config" / "token_gmail.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

def _get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def _header(headers, name):
    return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")

def _decode_body(payload):
    body = ""
    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode("utf-8", errors="replace")
    elif payload.get("parts"):
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                    break
    return body.strip()

def gmail_action(parameters: dict | None = None, **_: Any) -> str:
    params     = parameters or {}
    action     = params.get("action", "read")
    count      = int(params.get("count", 5))
    query      = params.get("query", "is:unread")
    to         = params.get("to", "")
    subject    = params.get("subject", "")
    body       = params.get("body", "")
    message_id = params.get("message_id", "")

    try:
        svc = _get_service()

        if action == "read":
            results  = svc.users().messages().list(userId="me", q=query, maxResults=count).execute()
            messages = results.get("messages", [])
            if not messages:
                return "Nenhum email encontrado, senhor."
            summaries = []
            for i, ref in enumerate(messages, 1):
                msg     = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
                headers = msg["payload"].get("headers", [])
                summaries.append(
                    f"{i}. De: {_header(headers,'From')}\n"
                    f"   Assunto: {_header(headers,'Subject')}\n"
                    f"   Data: {_header(headers,'Date')}\n"
                    f"   Prévia: {msg.get('snippet','')[:120]}"
                )
            return "Seus emails recentes:\n\n" + "\n\n".join(summaries)

        elif action == "send":
            if not to or not subject or not body:
                return "Preciso de: to, subject e body para enviar, senhor."
            msg = MIMEText(body)
            msg["to"] = to; msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            return f"Email enviado para {to}, senhor."

        elif action == "reply":
            if not message_id or not body:
                return "Preciso de message_id e body para responder, senhor."
            msg      = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            headers  = msg["payload"].get("headers", [])
            to_addr  = _header(headers, "From")
            subj     = _header(headers, "Subject")
            thread   = msg.get("threadId", "")
            orig     = _decode_body(msg["payload"])
            subj     = subj if subj.lower().startswith("re:") else f"Re: {subj}"
            quoted   = "\n".join(f"> {l}" for l in orig.splitlines())
            full     = f"{body}\n\n— Mensagem original —\n{quoted}"
            reply    = MIMEText(full)
            reply["to"] = to_addr; reply["subject"] = subj
            reply["In-Reply-To"] = message_id; reply["References"] = message_id
            raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
            svc.users().messages().send(userId="me", body={"raw": raw, "threadId": thread}).execute()
            return f"Resposta enviada para {to_addr}, senhor."

        elif action == "detail":
            if not message_id:
                return "Preciso do message_id, senhor."
            msg     = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            headers = msg["payload"].get("headers", [])
            return (
                f"De: {_header(headers,'From')}\n"
                f"Assunto: {_header(headers,'Subject')}\n"
                f"Data: {_header(headers,'Date')}\n\n"
                f"{_decode_body(msg['payload'])[:2000]}"
            )

        elif action == "mark_read":
            if not message_id:
                return "Preciso do message_id, senhor."
            svc.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds":["UNREAD"]}).execute()
            return "Email marcado como lido, senhor."

        else:
            return f"Ação desconhecida: {action}"

    except Exception as e:
        return f"Erro no Gmail: {e}"
