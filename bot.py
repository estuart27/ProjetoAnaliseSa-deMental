import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

import config
import database
from questions import BLOCOS, parse_tempo
from utils.ai_analyzer import gerar_resumo_semanal

log = logging.getLogger(__name__)

# chat_id -> (bloco, idx, data) : aguardando resposta em texto livre
_pendentes: dict[int, tuple] = {}
# chats que ativaram o /espaco: tudo que escrever vira anotação (até /fim)
_espaco: set[int] = set()

EMOJI = {"versiculo": "📖", "meditacao": "🧘", "exercicio": "🏃", "hobby": "🎨",
         "estudo": "📚", "terapia": "💬", "geral": "⏰"}
# ao tocar em "✅ Fiz", também marca o hábito correspondente no registro do dia
CAT_CAMPO = {"hobby": "hobby_feito", "exercicio": "exercicio_fisico", "estudo": "estudou_leu"}


# ---------- helpers ----------
def _opcoes(p):
    if p["tipo"] == "escala":
        return [(str(i), i) for i in range(p.get("min", 1), p.get("max", 5) + 1)]
    return p["opcoes"]


def _label(p, valor):
    return next((l for l, v in _opcoes(p) if v == valor), str(valor))


def _teclado(bloco, idx, data, p):
    botoes = [InlineKeyboardButton(l, callback_data=f"r|{bloco}|{idx}|{v}|{data}") for l, v in _opcoes(p)]
    por_linha = 6 if len(botoes) > 5 else len(botoes)
    return InlineKeyboardMarkup([botoes[i:i + por_linha] for i in range(0, len(botoes), por_linha)])


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


async def enviar_lembrete(bot, chat_id, lid):
    """Chamado pelo agendador para cada lembrete criado no painel."""
    l = database.get_lembrete(lid)
    if not l or not l["ativo"]:
        return
    txt = f"{EMOJI.get(l['categoria'], '⏰')} {l['titulo']}" + (f"\n\n{l['mensagem']}" if l["mensagem"] else "")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Fiz", callback_data=f"l|{lid}|{database.hoje()}")]])
    await bot.send_message(chat_id, txt, reply_markup=kb)


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
            await context.bot.send_message(chat_id, p.get("prompt", "O que houve? Escreva aqui:"))
            return
        database.salvar_resposta(data, p["campo"], "Nenhum")
    else:
        database.salvar_resposta(data, p["campo"], valor)
    await enviar_pergunta(context.bot, chat_id, bloco, idx + 1, data)


async def on_lembrete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != config.OWNER_CHAT_ID:
        await q.answer()
        return
    await q.answer("Anotado! 💪")
    try:
        _, lid, data = q.data.split("|")
        l = database.get_lembrete(int(lid))
    except ValueError:
        return
    if not l:
        return
    database.marcar_lembrete(l["id"], data)
    campo = CAT_CAMPO.get(l["categoria"])
    if campo:
        database.salvar_resposta(data, campo, 1)
    try:
        await q.edit_message_text(f"{EMOJI.get(l['categoria'], '⏰')} {l['titulo']}\n✅ Feito!")
    except Exception:
        pass


async def on_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto = update.message.text.strip()
    pend = _pendentes.pop(chat_id, None)
    if not pend:
        if chat_id in _espaco:
            database.salvar_espaco(texto)
            await update.message.reply_text("🫶 Guardado.")
            return
        await update.message.reply_text("Não estou esperando uma resposta agora. Use /hoje, /resumo, /noite ou /espaco.")
        return
    bloco, idx, data = pend
    p = BLOCOS[bloco]["perguntas"][idx]
    database.salvar_resposta(data, p["campo"], texto)
    if p.get("min_campo"):
        minutos = parse_tempo(texto)
        database.salvar_resposta(data, p["min_campo"], minutos)
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
            "/espaco – seu espaço livre de pensamentos (/fim para sair, /notas para ver)\n"
            "/evento – marcar algo relevante na linha do tempo\n"
            "/dashboard – link do painel (lembretes, metas e gráficos)\n/cancelar – cancelar resposta pendente")
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
    await update.message.reply_text("📋 Hoje:\n" + "\n".join(f"• {c}: {dia[c]}" for c in campos))


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_resumo_semanal(context.bot, update.effective_chat.id)


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.PUBLIC_URL:
        await update.message.reply_text("Defina PUBLIC_URL no .env (ex: https://meuapp.com). Local: http://localhost:8000/dashboard?key=SUA_SENHA")
        return
    await update.message.reply_text(f"{config.PUBLIC_URL}/dashboard?key={config.DASHBOARD_KEY}")


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _pendentes.pop(update.effective_chat.id, None)
    _espaco.discard(update.effective_chat.id)
    await update.message.reply_text("Ok, cancelado.")


async def cmd_espaco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/espaco -> abre o espaço (tudo que escrever é guardado) | /espaco texto -> guarda só aquela nota."""
    chat_id = update.effective_chat.id
    if context.args:
        database.salvar_espaco(" ".join(context.args))
        await update.message.reply_text("🫶 Guardado.")
        return
    _pendentes.pop(chat_id, None)
    _espaco.add(chat_id)
    await update.message.reply_text(
        "🕊️ Este é o seu espaço. Escreva livremente: pensamentos, reflexões, o que quiser.\n"
        "Eu só guardo (e a análise semanal usa isso para te entender melhor).\n"
        "Quando terminar: /fim")


async def cmd_fim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in _espaco:
        _espaco.discard(update.effective_chat.id)
        await update.message.reply_text("Espaço fechado. Obrigado por confiar. 🤍")
    else:
        await update.message.reply_text("O espaço não estava aberto. Use /espaco.")


async def cmd_notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notas = database.ultimas_notas(5)
    if not notas:
        await update.message.reply_text("Seu espaço ainda está vazio.")
        return
    await _enviar_longo(context.bot, update.effective_chat.id,
                        "🗒️ Últimas notas:\n\n" + "\n\n".join(f"[{n['data']}] {n['texto']}" for n in notas))


async def cmd_evento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/evento Título | descrição opcional  -> entra na linha do tempo do painel (hoje)."""
    bruto = " ".join(context.args).strip()
    if not bruto:
        await update.message.reply_text("Use: /evento Título | descrição (opcional)\nEx: /evento Conversa difícil com meu pai | senti alívio depois")
        return
    titulo, _, desc = (s.strip() for s in bruto.partition("|"))
    database.add_evento(database.hoje(), titulo[:120], desc[:1000])
    await update.message.reply_text("📌 Evento adicionado à sua linha do tempo.")


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    owner = filters.User(user_id=config.OWNER_CHAT_ID if config.OWNER_CHAT_ID else -1)

    app.add_handler(CommandHandler("start", cmd_start))
    for b in BLOCOS:
        app.add_handler(CommandHandler(b, _cmd_bloco(b), filters=owner))
    for nome, fn in (("hoje", cmd_hoje), ("resumo", cmd_resumo), ("dashboard", cmd_dashboard),
                     ("cancelar", cmd_cancelar), ("espaco", cmd_espaco), ("fim", cmd_fim),
                     ("notas", cmd_notas), ("evento", cmd_evento)):
        app.add_handler(CommandHandler(nome, fn, filters=owner))
    app.add_handler(CallbackQueryHandler(on_resposta, pattern=r"^r\|"))
    app.add_handler(CallbackQueryHandler(on_lembrete, pattern=r"^l\|"))
    app.add_handler(MessageHandler(owner & filters.TEXT & ~filters.COMMAND, on_texto))
    return app