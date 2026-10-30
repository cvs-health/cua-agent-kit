# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import logging
import os


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise SystemExit("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("cua_agent_kit").setLevel(level)
    events = logging.getLogger("cua_agent_kit.events")
    if not events.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        events.addHandler(handler)
    events.setLevel(logging.INFO)
    events.propagate = False
    logging.getLogger(__name__).info("Console logging configured")
