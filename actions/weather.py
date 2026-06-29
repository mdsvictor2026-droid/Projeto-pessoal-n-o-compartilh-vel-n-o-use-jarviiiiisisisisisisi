"""actions/weather.py — Clima via OpenWeatherMap"""
from __future__ import annotations
import os
from typing import Any

def get_weather(parameters: dict | None = None, **_: Any) -> str:
    params = parameters or {}
    city   = params.get("city", "").strip()
    if not city:
        return "Preciso do nome da cidade, senhor."
    try:
        import requests
        key = os.environ.get("OPENWEATHER_API_KEY", "")
        if not key:
            return "Chave da OpenWeatherMap não configurada."
        url  = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&units=metric&lang=pt_br"
        data = requests.get(url, timeout=10).json()
        if data.get("cod") != 200:
            return f"Cidade não encontrada: {city}"
        desc  = data["weather"][0]["description"].capitalize()
        temp  = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        hum   = data["main"]["humidity"]
        wind  = data["wind"]["speed"]
        return (
            f"Clima em {data['name']}, {data['sys']['country']}:\n"
            f"  {desc}\n"
            f"  Temperatura: {temp:.1f}°C (sensação {feels:.1f}°C)\n"
            f"  Umidade: {hum}%\n"
            f"  Vento: {wind} m/s"
        )
    except Exception as e:
        return f"Erro ao buscar clima: {e}"