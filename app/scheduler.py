from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .config_manager import config_state
from .googlechat import chat_send
import logging


def init_scheduler():
    sched = AsyncIOScheduler()

    @sched.scheduled_job("interval", minutes=60)
    async def periodic_promote_check():
        try:
            await config_state.maybe_auto_promote()
        except Exception as e:
            logging.error(f"Promote check error: {e}")

    @sched.scheduled_job("interval", hours=24)
    async def daily_heartbeat():
        await chat_send(
            ":information_source: Browser Update Controller heartbeat OK.")

    sched.start()
    return sched
