from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import bot
import config
import database

OPTS = dict(misfire_grace_time=1800, coalesce=True)


def _hm(s: str):
    h, m = s.strip().split(":")
    return int(h), int(m)


def sincronizar_lembretes(sched, tg_bot):
    """Recria os jobs dos lembretes a partir do banco. Chamado na partida e a cada mudança no painel."""
    for j in sched.get_jobs():
        if j.id.startswith("lem_"):
            j.remove()
    for l in database.listar_lembretes(apenas_ativos=True):
        h, m = _hm(l["horario"])
        extra = {"day_of_week": l["dias"]} if l["tipo"] == "semanal" and l["dias"] else {}
        sched.add_job(bot.enviar_lembrete, CronTrigger(hour=h, minute=m, **extra),
                      args=[tg_bot, config.OWNER_CHAT_ID, l["id"]], id=f"lem_{l['id']}", **OPTS)


def criar_scheduler(ptb) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=config.TIMEZONE)

    for bloco, hhmm in config.HORARIOS.items():
        h, m = _hm(hhmm)
        sched.add_job(bot.enviar_bloco, CronTrigger(hour=h, minute=m),
                      args=[ptb.bot, config.OWNER_CHAT_ID, bloco], id=f"bloco_{bloco}", **OPTS)

    dia, hhmm = config.RESUMO_SEMANAL.split()
    h, m = _hm(hhmm)
    sched.add_job(bot.enviar_resumo_semanal, CronTrigger(day_of_week=dia, hour=h, minute=m),
                  args=[ptb.bot, config.OWNER_CHAT_ID], id="resumo_semanal", **OPTS)

    sincronizar_lembretes(sched, ptb.bot)
    return sched