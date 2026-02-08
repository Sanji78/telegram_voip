from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CALL_ST_IDLE,
    SENSOR_CALL_PEER,
    SENSOR_CALL_STATE,
    SENSOR_CALL_TOPIC,
    SENSOR_LAST_ERROR,
    DOMAIN,
)


class TelegramVoipCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass=hass,
            logger=logging.getLogger(__name__),
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,  # push-based
        )
        self.data = {
            SENSOR_CALL_STATE: CALL_ST_IDLE,
            SENSOR_CALL_TOPIC: None,
            SENSOR_CALL_PEER: None,
            SENSOR_LAST_ERROR: None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _async_update_data(self) -> dict[str, Any]:
        return self.data

    def set_state(self, **kwargs: Any) -> None:
        self.data.update(kwargs)
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Schedule state update on the main event loop
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)