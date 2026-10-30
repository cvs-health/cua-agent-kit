# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import signal

from aiohttp import web
from dotenv import load_dotenv

from cua_agent_kit.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def serve() -> None:
    state = {"status": "running"}
    stopped = asyncio.Event()

    async def health(request: web.Request) -> web.Response:
        return web.json_response(state)

    async def ready(request: web.Request) -> web.Response:
        return web.json_response(
            state, status=503 if state["status"] in {"failed", "stopping"} else 200
        )

    app = web.Application()
    app.router.add_get("/health/live", health)
    app.router.add_get("/health/ready", ready)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 8080).start()
    loop = asyncio.get_running_loop()
    for shutdown_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(shutdown_signal, stopped.set)
    process = None
    try:
        process = await asyncio.create_subprocess_exec("cua-agent-run")

        async def watch_run() -> None:
            return_code = await process.wait()
            if not stopped.is_set():
                state["status"] = "completed" if return_code == 0 else "failed"
            logger.log(
                logging.INFO if return_code == 0 or stopped.is_set() else logging.ERROR,
                "Workflow %s; exit code %s",
                state["status"],
                return_code,
            )

        watcher = asyncio.create_task(watch_run())
        try:
            await stopped.wait()
        finally:
            state["status"] = "stopping"
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=30)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            await watcher
    finally:
        await runner.cleanup()


def main() -> None:
    load_dotenv()
    configure_logging()
    asyncio.run(serve())
