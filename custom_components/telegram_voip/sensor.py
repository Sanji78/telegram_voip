from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_CALL_STATE,
    SENSOR_CALL_TOPIC,
    SENSOR_CALL_PEER,
    SENSOR_LAST_ERROR,
    CONF_SESSION_NAME,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    session_name = entry.data.get(CONF_SESSION_NAME, "telegram_voip")

    async_add_entities(
        [
            TelegramVoipSensor(coordinator, entry, session_name, SENSOR_CALL_STATE, "call_state"),
            TelegramVoipSensor(coordinator, entry, session_name, SENSOR_CALL_TOPIC, "call_topic"),
            TelegramVoipSensor(coordinator, entry, session_name, SENSOR_CALL_PEER, "call_peer"),
            TelegramVoipSensor(coordinator, entry, session_name, SENSOR_LAST_ERROR, "last_error"),
        ],
        update_before_add=True,
    )


class TelegramVoipSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, session_name: str, key: str, translation_key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": session_name,
        }
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = translation_key
        self._attr_has_entity_name = True
        self._attr_suggested_object_id = f"{session_name}_{translation_key}"

        
    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)