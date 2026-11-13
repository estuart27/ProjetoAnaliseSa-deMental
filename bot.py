import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

import config
import database
from questions import BLOCOS, parse_tempo_tela
from utils.ai_analyzer import gerar_resumo_semanal

log = logging.getLogger(__name__)

# chat_id -> (bloco, idx, data) : aguardando resposta em texto livre
_pendentes: dict[int, tuple] = {}


# ---------- helpers ----------
def _opcoes(p):
    return [(str(i), i) for i in range(1, 6)] if p["tipo"] == "escala" else p["opcoes"]


def _label(p, valor):
    return next((l for l, v in _opcoes(p) if v == valor), str(valor))


def _teclado(bloco, idx, data, p):
    botoes = [InlineKeyboardButton(l, callback_data=f"r|{bloco}|{idx}|{v}|{data}") for l, v in _opcoes(p)]
    return InlineKeyboardMarkup([botoes])


async def _enviar_longo(bot, chat_id, texto):
    for i in range(0, len(texto), 4000):
        await bot.send_message(chat_id, texto[i:i + 4000])


async def enviar_pergunta(bot, chat_id, bloco, idx, data):
    perguntas = BLOCOS[bloco]["perguntas"]
    if idx >= len(perguntas):
        await bot.send_message(chat_id, "✅ Bloco concluído. Obrigado por se registrar. 🙏")
        return
    p = perguntas[idx]
    prefixo = f"({idx + 1}/{len(perguntas)}) "
    if p["tipo"] == "texto":
        _pendentes[chat_id] = (bloco, idx, data)
        await bot.send_message(chat_id, prefixo + p["texto"])
        return
    texto = prefixo + p["texto"] + (f"\n{p['legenda']}" if p.get("legenda") else "")
    await bot.send_message(chat_id, texto, reply_markup=_teclado(bloco, idx, data, p))


async def enviar_bloco(bot, chat_id, bloco):
    """Chamado pelo agendador (e pelos comandos /manha /tarde /noite)."""
    _pendentes.pop(chat_id, None)
    await bot.send_message(chat_id, BLOCOS[bloco]["titulo"])
    await enviar_pergunta(bot, chat_id, bloco, 0, database.hoje())


async def enviar_resumo_semanal(bot, chat_id):
    await bot.send_message(chat_id, "📊 Preparando seu resumo da semana...")
    await _enviar_longo(bot, chat_id, await gerar_resumo_semanal(7))


# ---------- handlers ----------
async def on_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != config.OWNER_CHAT_ID:
        return
    try:
        _, bloco, idx, valor, data = q.data.split("|")
        idx, valor = int(idx), int(valor)
        p = BLOCOS[bloco]["perguntas"][idx]
    except (ValueError, KeyError, IndexError):
        return

    chat_id = q.message.chat_id
    try:
        await q.edit_message_text(f"{p['texto']}\n➡️ {_label(p, valor)}")
    except Exception:
        pass

    if p["tipo"] == "imprevisto":
        if valor == 1:
            _pendentes[chat_id] = (bloco, idx, data)
            await context.bot.send_message(chat_id, "O que houve? Escreva aqui:")
            return
        database.salvar_resposta(data, p["campo"], "Nenhum")
    else:
        database.salvar_resposta(data, p["campo"], valor)
    await enviar_pergunta(context.bot, chat_id, bloco, idx + 1, data)


async def on_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    pend = _pendentes.pop(chat_id, None)
    if not pend:
        await update.message.reply_text("Não estou esperando uma resposta agora. Use /hoje, /resumo ou /noite.")
        return
    bloco, idx, data = pend
    p = BLOCOS[bloco]["perguntas"][idx]
    texto = update.message.text.strip()
    database.salvar_resposta(data, p["campo"], texto)
    if p["campo"] == "tempo_tela":
        minutos = parse_tempo_tela(texto)
        database.salvar_resposta(data, "tempo_tela_min", minutos)
        if minutos is None:
            await update.message.reply_text("Salvei, mas não entendi o formato (use ex: 4h 30m) — não vai entrar no gráfico.")
    await update.message.reply_text("📝 Anotado.")
    await enviar_pergunta(context.bot, chat_id, bloco, idx + 1, data)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if config.OWNER_CHAT_ID and uid != config.OWNER_CHAT_ID:
        return  # bot privado: ignora estranhos
    msg = f"Olá! Seu chat id é: {uid}\n"
    if not config.OWNER_CHAT_ID:
        msg += "Coloque esse número em OWNER_CHAT_ID no .env e reinicie o app.\n"
    msg += ("\nComandos:\n/manha /tarde /noite – responder um bloco agora\n"
            "/hoje – ver o que registrei hoje\n/resumo – análise da semana (IA)\n"
            "/dashboard – link do painel\n/cancelar – cancelar resposta pendente")
    await update.message.reply_text(msg)


def _cmd_bloco(bloco):
    async def _h(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await enviar_bloco(context.bot, update.effective_chat.id, bloco)
    return _h


async def cmd_hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dia = database.get_dia(database.hoje())
    if not dia:
        await update.message.reply_text("Nada registrado hoje ainda.")
        return
    campos = [c for c in dia if c not in ("id", "created_at", "updated_at", "data") and dia[c] is not None]
    linhas = [f"• {c}: {dia[c]}" for c in campos]
    await update.message.reply_text("📋 Hoje:\n" + "\n".join(linhas))


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_resumo_semanal(context.bot, update.effective_chat.id)


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.PUBLIC_URL:
        await update.message.reply_text("Defina PUBLIC_URL no .env (ex: https://meuapp.com). Local: http://localhost:8000/dashboard?key=SUA_SENHA")
        return
    await update.message.reply_text(f"{config.PUBLIC_URL}/dashboard?key={config.DASHBOARD_KEY}")


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _pendentes.pop(update.effective_chat.id, None)
    await update.message.reply_text("Ok, cancelado.")


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    owner = filters.User(user_id=config.OWNER_CHAT_ID if config.OWNER_CHAT_ID else -1)

    app.add_handler(CommandHandler("start", cmd_start))
    for b in BLOCOS:
        app.add_handler(CommandHandler(b, _cmd_bloco(b), filters=owner))
    app.add_handler(CommandHandler("hoje", cmd_hoje, filters=owner))
    app.add_handler(CommandHandler("resumo", cmd_resumo, filters=owner))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard, filters=owner))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar, filters=owner))
    app.add_handler(CallbackQueryHandler(on_resposta, pattern=r"^r\|"))
    app.add_handler(MessageHandler(owner & filters.TEXT & ~filters.COMMAND, on_texto))
    return app
