import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from telegram import Update

import bot
import config
import database
from scheduler import criar_scheduler

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
    if sched:
        sched.start()
        log.info("Agendador iniciado: %s", config.HORARIOS)
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


def _checar_chave(key: str):
    if not config.DASHBOARD_KEY:
        raise HTTPException(503, "Defina DASHBOARD_KEY no .env")
    if not secrets.compare_digest(key.encode(), config.DASHBOARD_KEY.encode()):
        raise HTTPException(401, "Chave inválida")

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
