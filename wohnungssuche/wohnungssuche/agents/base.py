"""Agent foundation.

Every agent logs start, completion and duration, and turns an exception into an
error message on the outgoing envelope instead of raising: one broken agent
degrades the run, it does not end it (lesson 7 of the build brief).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from wohnungssuche.config import SearchConfig
from wohnungssuche.models import AgentMessage

LOGGER = logging.getLogger(__name__)


@dataclass
class BaseAgent(ABC):
    config: SearchConfig
    name: str = "agent"

    @abstractmethod
    def execute(self, message: AgentMessage) -> Dict[str, Any]:
        """Do the work and return the payload for the next agent."""

    def run(self, message: AgentMessage) -> AgentMessage:
        LOGGER.info("[%s] start", self.name)
        started = time.monotonic()
        errors = []
        try:
            payload = self.execute(message)
        except Exception as exc:  # noqa: BLE001 - deliberate catch-all
            LOGGER.exception("[%s] failed: %s", self.name, exc)
            errors.append(f"{type(exc).__name__}: {exc}")
            # Hand the input through unchanged so later agents still have data.
            payload = dict(message.payload)
        duration = time.monotonic() - started
        LOGGER.info(
            "[%s] done in %.2fs (%s)",
            self.name,
            duration,
            "ok" if not errors else "with errors",
        )
        return AgentMessage(
            sender=self.name,
            recipient="orchestrator",
            payload=payload,
            errors=errors,
            duration_seconds=round(duration, 3),
        )
