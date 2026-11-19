import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

def call(method, path, **kwargs):
    base = os.getenv("KEITARO_URL", "").rstrip("/")
    key = os.getenv("KEITARO_API_KEY")
    if not base or not key:
        raise HTTPException(503, "Настройте KEITARO_URL и KEITARO_API_KEY в .env")
    try:
        response = httpx.request(method, base + "/admin_api/v1/" + path,
                                 headers={"Api-Key": key}, timeout=15, **kwargs)
    except httpx.RequestError as exc:
        raise HTTPException(502, "Keitaro не ответил. Результат операции неизвестен.") from exc
    if not response.is_success:
        raise HTTPException(502, f"Keitaro: {method} {path}, HTTP {response.status_code}")
    return response.json() if response.content else None
