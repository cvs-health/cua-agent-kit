# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Disposable local demo with synthetic referrals and page-local appointments."""

from pathlib import Path

from aiohttp import web


async def index(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(Path(__file__).with_name("index.html"))


async def asset(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(Path(__file__).with_name(request.path.removeprefix("/")))


def main() -> None:
    app = web.Application()
    app.router.add_get("/", index)
    for filename in ("styles.css", "app.js", "data.json"):
        app.router.add_get(f"/{filename}", asset)
    web.run_app(app, host="127.0.0.1", port=8081)


if __name__ == "__main__":
    main()
