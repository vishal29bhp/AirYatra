"""AirYatra background worker: runs the APScheduler jobs in exactly one process.

On Azure this is the single-replica ``worker`` container app (SCHEDULER_ENABLED=true); the API replicas
run with SCHEDULER_ENABLED=false so no job fires once per replica (master prompt Q.2 item 10).

    python worker.py
"""
import asyncio
import logging
import signal

from database import close_mongo_connection, connect_to_mongo
from scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger("airyatra.worker")


class SchedulerWorker:
    """Owns the worker lifecycle: connect, start jobs, wait for a stop signal, shut down cleanly."""

    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.request_stop)
            except NotImplementedError:  # pragma: no cover - Windows
                pass

    async def run(self) -> None:
        await connect_to_mongo()
        start_scheduler()
        logger.info("AirYatra worker started; scheduler running")
        try:
            await self._stop.wait()
        finally:
            stop_scheduler()
            await close_mongo_connection()
            logger.info("AirYatra worker stopped")


async def _main() -> None:
    worker = SchedulerWorker()
    worker.install_signal_handlers(asyncio.get_running_loop())
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(_main())
