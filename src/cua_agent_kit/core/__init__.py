# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Shared browser and artifact infrastructure."""

from cua_agent_kit.core.artifacts import RunArtifacts
from cua_agent_kit.core.browser import BrowserSession

__all__ = ["BrowserSession", "RunArtifacts"]
