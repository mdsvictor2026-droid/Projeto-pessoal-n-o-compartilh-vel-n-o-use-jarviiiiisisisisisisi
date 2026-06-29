"""actions/code_helper.py — Ajuda com código via Gemini"""
from __future__ import annotations
import os
from typing import Any

def code_helper(parameters: dict | None = None, **_: Any) -> str:
    params   = parameters or {}
    task     = params.get("task", "").strip()
    language = params.get("language", "Python")
    code     = params.get("code", "")

    if not task:
        return "Preciso de uma descrição da tarefa, senhor."

    try:
        from google import genai  # type: ignore[import-not-found,attr-defined]
        key = os.environ["GEMINI_API_KEY"]
        client = genai.Client(api_key=key)  # type: ignore[attr-defined]
        prompt = f"Language: {language}\nTask: {task}"
        if code:
            prompt += f"\n\nExisting code:\n```{language}\n{code}\n```"
        response = client.models.generate_content(  # type: ignore[attr-defined]
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text or "Sem resposta do modelo."
    except Exception as e:
        return f"Erro no code_helper: {e}"
