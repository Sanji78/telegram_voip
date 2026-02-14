import asyncio
import os
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

from .const import (
    DOMAIN,
)
from .coordinator import TelegramVoipCoordinator
from .voip_manager import TelegramVoipManager
from .pyrogram_compat import patch_pyrogram_send

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    patch_pyrogram_send()
    session_dir = entry.options.get("session_dir", entry.data.get("session_dir", "/config/.telegram_voip"))
    await hass.async_add_executor_job(lambda: os.makedirs(session_dir, exist_ok=True))
    
    coordinator = TelegramVoipCoordinator(hass, entry)
    manager = TelegramVoipManager(hass, entry, coordinator)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "manager": manager,
    }

    # Register services PER ENTRY (not globally)
    async def svc_call(call: ServiceCall) -> None:
        """Handle call service - route to correct manager based on device/entity target."""
        try:
            # Get the target device/entity if specified
            target_devices = call.data.get("device_id", [])
            target_entities = call.data.get("entity_id", [])
            
            # Find which manager to use
            target_manager = None
            
            if target_devices:
                # Find entry that owns this device
                device_reg = dr.async_get(hass)
                for device_id in target_devices if isinstance(target_devices, list) else [target_devices]:
                    device = device_reg.async_get(device_id)
                    if device:
                        for entry_id in device.config_entries:
                            if entry_id in hass.data[DOMAIN]:
                                target_manager = hass.data[DOMAIN][entry_id]["manager"]
                                break
            
            if target_entities:
                # Find entry that owns this entity
                from homeassistant.helpers import entity_registry as er
                entity_reg = er.async_get(hass)
                for entity_id in target_entities if isinstance(target_entities, list) else [target_entities]:
                    entity = entity_reg.async_get(entity_id)
                    if entity and entity.config_entry_id in hass.data[DOMAIN]:
                        target_manager = hass.data[DOMAIN][entity.config_entry_id]["manager"]
                        break
            
            # If no target specified, use this entry's manager (backward compatibility)
            if not target_manager:
                target_manager = manager
            
            # Call with the correct manager
            await target_manager.async_call(**{k: v for k, v in call.data.items() 
                                               if k not in ["device_id", "entity_id"]})
        except ValueError as e:
            _LOGGER.error("Invalid call parameters: %s", str(e))
            raise HomeAssistantError(str(e)) from e
        except RuntimeError as e:
            _LOGGER.warning("Call error: %s", str(e))
            raise HomeAssistantError(str(e)) from e
        except Exception as e:
            _LOGGER.exception("Unexpected error during call")
            raise HomeAssistantError(f"Call failed: {str(e)}") from e
        
    async def svc_hangup(call: ServiceCall) -> None:
        """Handle hangup service - route to correct manager."""
        target_devices = call.data.get("device_id", [])
        target_entities = call.data.get("entity_id", [])
        
        target_manager = None
        
        if target_devices:
            device_reg = dr.async_get(hass)
            for device_id in target_devices if isinstance(target_devices, list) else [target_devices]:
                device = device_reg.async_get(device_id)
                if device:
                    for entry_id in device.config_entries:
                        if entry_id in hass.data[DOMAIN]:
                            target_manager = hass.data[DOMAIN][entry_id]["manager"]
                            break
        
        if target_entities:
            from homeassistant.helpers import entity_registry as er
            entity_reg = er.async_get(hass)
            for entity_id in target_entities if isinstance(target_entities, list) else [target_entities]:
                entity = entity_reg.async_get(entity_id)
                if entity and entity.config_entry_id in hass.data[DOMAIN]:
                    target_manager = hass.data[DOMAIN][entity.config_entry_id]["manager"]
                    break
        
        if not target_manager:
            target_manager = manager
            
        await target_manager.async_hangup()

    # Register services once globally (will be shared by all instances)
    if not hass.services.has_service(DOMAIN, "call"):
        hass.services.async_register(
            DOMAIN, 
            "call", 
            svc_call, 
            supports_response=SupportsResponse.NONE
        )

    if not hass.services.has_service(DOMAIN, "hangup"):
        hass.services.async_register(
            DOMAIN, 
            "hangup", 
            svc_hangup, 
            supports_response=SupportsResponse.NONE
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Get session name for device identification
    from .const import CONF_SESSION_NAME
    session_name = entry.data.get(CONF_SESSION_NAME, "telegram_voip")

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Telegram",
        # name=f"Telegram VoIP ({session_name})",
        name=session_name,
        model="Pyrogram + tgvoip",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data:
        await data["manager"].async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # Only remove services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "call")
            hass.services.async_remove(DOMAIN, "hangup")
            
    return unload_ok