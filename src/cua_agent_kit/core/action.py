# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Action:
    """An action the agent performed."""

    action: str
    outcome: str = "success"
    details: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] | None = None
    url: str | None = None
    screenshot: bytes | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
