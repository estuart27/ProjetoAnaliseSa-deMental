import datetime as dt
import logging
import secrets
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telegram import Update

import bot
import config
import database
from scheduler import criar_scheduler, sincronizar_lembretes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Defina TELEGRAM_BOT_TOKEN no .env")
    database.init_db()

    ptb = bot.build_application()
    app.state.ptb = ptb
    await ptb.initialize()
    await ptb.start()

    if config.BOT_MODE == "webhook":
        await ptb.bot.set_webhook(url=f"{config.WEBHOOK_URL}/telegram/webhook",
                                  secret_token=config.WEBHOOK_SECRET or None)
        log.info("Bot em modo WEBHOOK")
    else:
        await ptb.bot.delete_webhook()
        await ptb.updater.start_polling(drop_pending_updates=True)
        log.info("Bot em modo POLLING")

    sched = criar_scheduler(ptb) if config.OWNER_CHAT_ID else None
    app.state.sched = sched
    if sched:
        sched.start()
        log.info("Agendador iniciado: %s + %d lembretes", config.HORARIOS, len(database.listar_lembretes(True)))
    else:
        log.warning("OWNER_CHAT_ID não definido: mande /start ao bot, copie o id para o .env e reinicie.")

    yield

    if sched:
        sched.shutdown(wait=False)
    if config.BOT_MODE != "webhook":
        await ptb.updater.stop()
    await ptb.stop()
    await ptb.shutdown()


app = FastAPI(title="Tracking Pessoal", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

DiaSemana = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class LembreteIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=80)
    mensagem: str = Field(default="", max_length=1000)
    categoria: Literal["versiculo", "meditacao", "exercicio", "hobby", "estudo", "terapia", "geral"] = "geral"
    tipo: Literal["diario", "semanal"]
    dias: list[DiaSemana] = []
    horario: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class EventoIn(BaseModel):
    data: dt.date
    titulo: str = Field(min_length=1, max_length=120)
    descricao: str = Field(default="", max_length=1000)
    categoria: Literal["conquista", "dificil", "saude", "relacionamento", "trabalho", "geral"] = "geral"


def _checar_chave(key: str):
    if not config.DASHBOARD_KEY:
        raise HTTPException(503, "Defina DASHBOARD_KEY no .env")
    if not secrets.compare_digest(key.encode(), config.DASHBOARD_KEY.encode()):
        raise HTTPException(401, "Chave inválida")


def _sync(request: Request):
    """Reagenda os lembretes depois de qualquer mudança feita pelo painel."""
    sched = request.app.state.sched
    if sched:
        sincronizar_lembretes(sched, request.app.state.ptb.bot)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(config.BASE_DIR / "static" / "favicon.ico")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if config.WEBHOOK_SECRET and not secrets.compare_digest(
            request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), config.WEBHOOK_SECRET):
        raise HTTPException(403)
    ptb = request.app.state.ptb
    update = Update.de_json(await request.json(), ptb.bot)
    await ptb.update_queue.put(update)
    return {"ok": True}


@app.get("/dashboard")
async def dashboard(key: str = ""):
    _checar_chave(key)
    return FileResponse(config.BASE_DIR / "templates" / "dashboard.html")


@app.get("/api/dados")
async def api_dados(key: str = "", dias: int = 14):
    _checar_chave(key)
    return database.get_serie(max(1, min(dias, 90)))


@app.get("/api/streak")
async def api_streak(key: str = ""):
    _checar_chave(key)
    return database.streak("pornografia")


@app.get("/api/habitos")
async def api_habitos(key: str = "", dias: int = 30):
    _checar_chave(key)
    return database.habitos_resumo(max(1, min(dias, 90)))


# ---------- lembretes ----------
@app.get("/api/lembretes")
async def api_lembretes(key: str = ""):
    _checar_chave(key)
    return database.listar_lembretes()


@app.post("/api/lembretes")
async def api_criar_lembrete(l: LembreteIn, request: Request, key: str = ""):
    _checar_chave(key)
    if l.tipo == "semanal" and not l.dias:
        raise HTTPException(422, "Escolha ao menos um dia da semana")
    lid = database.add_lembrete(l.titulo, l.mensagem, l.categoria, l.tipo, l.dias, l.horario)
    _sync(request)
    return {"id": lid}


@app.post("/api/lembretes/{lid}/toggle")
async def api_toggle_lembrete(lid: int, request: Request, key: str = ""):
    _checar_chave(key)
    database.toggle_lembrete(lid)
    _sync(request)
    return {"ok": True}


@app.delete("/api/lembretes/{lid}")
async def api_del_lembrete(lid: int, request: Request, key: str = ""):
    _checar_chave(key)
    database.del_lembrete(lid)
    _sync(request)
    return {"ok": True}


# ---------- linha do tempo ----------
@app.get("/api/eventos")
async def api_eventos(key: str = "", dias: int = 90):
    _checar_chave(key)
    return database.listar_eventos(max(1, min(dias, 365)))


@app.post("/api/eventos")
async def api_criar_evento(e: EventoIn, key: str = ""):
    _checar_chave(key)
    return {"id": database.add_evento(e.data.isoformat(), e.titulo, e.descricao, e.categoria)}


@app.delete("/api/eventos/{eid}")
async def api_del_evento(eid: int, key: str = ""):
    _checar_chave(key)
    database.del_evento(eid)
    return {"ok": True}