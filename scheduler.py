from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import bot
import config


def _hm(s: str):
    h, m = s.strip().split(":")
    return int(h), int(m)


def criar_scheduler(ptb) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=config.TIMEZONE)
    opts = dict(misfire_grace_time=1800, coalesce=True)

    for bloco, hhmm in config.HORARIOS.items():
        h, m = _hm(hhmm)
        sched.add_job(bot.enviar_bloco, CronTrigger(hour=h, minute=m),
                      args=[ptb.bot, config.OWNER_CHAT_ID, bloco], id=f"bloco_{bloco}", **opts)

    dia, hhmm = config.RESUMO_SEMANAL.split()
    h, m = _hm(hhmm)
    sched.add_job(bot.enviar_resumo_semanal, CronTrigger(day_of_week=dia, hour=h, minute=m),
                  args=[ptb.bot, config.OWNER_CHAT_ID], id="resumo_semanal", **opts)
    return sched
