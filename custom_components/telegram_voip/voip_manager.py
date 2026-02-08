from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import logging
from typing import Optional, Any
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

import re

from .const import (
    CALL_ST_ENDING,
    CALL_ST_ERROR,
    CALL_ST_IDLE,
    CALL_ST_IN_CALL,
    CALL_ST_RINGING,
    CALL_ST_STARTING,
    CONF_API_HASH,
    CONF_API_ID,
    CONF_BUF_SIZE,
    CONF_DEFAULT_LANGUAGE,
    CONF_DEFAULT_TARGET,
    CONF_FFMPEG_PATH,
    CONF_INIT_BITRATE,
    CONF_MAX_BITRATE,
    CONF_MAX_DURATION,
    CONF_MIN_BITRATE,
    CONF_PROFILE_PHOTO,
    CONF_PROFILE_NAME,
    CONF_RING_TIMEOUT,
    CONF_SESSION_DIR,
    CONF_SESSION_NAME,
    CONF_TIMEOUT,
    DEFAULT_BUF_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_INIT_BITRATE,
    DEFAULT_MAX_BITRATE,
    DEFAULT_MAX_DURATION,
    DEFAULT_MIN_BITRATE,
    DEFAULT_RING_TIMEOUT,
    DEFAULT_TIMEOUT,
    SENSOR_CALL_PEER,
    SENSOR_CALL_STATE,
    SENSOR_CALL_TOPIC,
    SENSOR_LAST_ERROR,
    SUPPORTED_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)


class TelegramVoipManager:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator

        self._client = None
        self._voip_service = None
        self._call = None

        self._call_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._call_state_raw: str | None = None

    @staticmethod
    def _make_tempdir() -> str:
        return tempfile.mkdtemp(prefix="ha_telegram_voip_")

    @staticmethod
    def _cleanup_tempdir(path: str) -> None:
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    def _is_terminal_state(self, st: str) -> bool:
        s = (st or "").lower()
        return any(x in s for x in ("busy", "failed", "ended", "discard", "hangup", "closed"))
    
    def _session_file_path(self) -> str:
        session_name = self._get_cfg(CONF_SESSION_NAME, "ha_telegram_voip")
        session_dir = self._get_cfg(CONF_SESSION_DIR, "/config/.telegram_voip")
        return os.path.join(session_dir, f"{session_name}.session")

    def _get_cfg(self, key: str, default=None):
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    async def async_shutdown(self) -> None:
        import gc
        await self.async_hangup()
        if self._client is not None:
            try:
                await asyncio.sleep(0.5)
                await self._client.stop()
                _LOGGER.info("Pyrogram client stopped")
            except Exception as ex:
                _LOGGER.error(f"Error stopping Pyrogram client: {ex}")
        self._client = None
        self._voip_service = None
        self._call = None
        await asyncio.sleep(0.5)
        gc.collect()
        _LOGGER.info("After gc.collect()")
    
    async def async_hangup(self) -> None:
        _LOGGER.info("Pyrogram hangup")
        self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_ENDING})
        if self._call is not None:
            try:
                discard = getattr(self._call, "discard", None)
                if callable(discard):
                    discard()
                stop = getattr(self._call, "stop", None)
                if callable(stop):
                    stop()
            except Exception as e:
                self.coordinator.set_state(**{SENSOR_LAST_ERROR: str(e)})

        self._stop_event.set()
        if self._call_task:
            try:
                await asyncio.wait_for(self._call_task, timeout=10)
            except Exception:
                pass
        self._call_task = None
        self._call = None
        self._call_state_raw = None 
        self._stop_event = asyncio.Event()
        self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_IDLE})

    async def async_call(
        self,
        message: str,
        target: Optional[str] = None,
        topic: Optional[str] = None,
        language: Optional[str] = None,
        image: Optional[str] = None,
        ring_timeout: Optional[int] = None,
        max_duration: Optional[int] = None,
    ) -> None:
        if self._call_task and not self._call_task.done():
            raise RuntimeError("A call is already in progress")

        target = target or self._get_cfg(CONF_DEFAULT_TARGET)
        if not target:
            raise ValueError("Missing target")

        language = (language or self._get_cfg(CONF_DEFAULT_LANGUAGE, DEFAULT_LANGUAGE)).lower()
        if language not in SUPPORTED_LANGUAGES:
            # Suggest close matches for common typos
            suggestions = {
                'jp': 'ja',  # Japanese
                'cn': 'zh',  # Chinese
                'eng': 'en', # English
                'ita': 'it', # Italian
                'esp': 'es', # Spanish
                'fra': 'fr', # French
                'deu': 'de', # German
                'por': 'pt', # Portuguese
            }
            
            suggestion = suggestions.get(language, None)
            if suggestion:
                raise ValueError(
                    f"Unsupported language: '{language}'. Did you mean '{suggestion}'? "
                    f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
                )
            else:
                raise ValueError(
                    f"Unsupported language: '{language}'. "
                    f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
                )

        ring_timeout = int(ring_timeout or self._get_cfg(CONF_RING_TIMEOUT, DEFAULT_RING_TIMEOUT))
        max_duration = int(max_duration or self._get_cfg(CONF_MAX_DURATION, DEFAULT_MAX_DURATION))

        self.coordinator.set_state(
            **{
                SENSOR_CALL_STATE: CALL_ST_STARTING,
                SENSOR_CALL_PEER: target,
                SENSOR_CALL_TOPIC: topic or message,
                SENSOR_LAST_ERROR: None,
            }
        )

        self._call_task = self.hass.async_create_task(
            self._async_run_call(
                target=target,
                message=message,
                topic=topic,
                language=language,
                image=image,
                ring_timeout=ring_timeout,
                max_duration=max_duration,
            )
        )

    async def _resolve_target(self, target: str) -> Any:
        t = (target or "").strip()
        if not t:
            raise ValueError("Missing target")

        if t.isdigit():
            return int(t)

        if t.startswith("@") or re.fullmatch(r"[A-Za-z0-9_]{5,32}", t):
            username = t if t.startswith("@") else f"@{t}"
            try:
                user = await self._client.get_users(username)
                return user.id if hasattr(user, "id") else username
            except Exception:
                return username

        digits = re.sub(r"[^\d+]", "", t)
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        if not digits.startswith("+"):
            raise ValueError("Phone numbers must be in international format, e.g. +393331112233")

        from pyrogram.raw.types import InputPhoneContact
        profile_name = self._get_cfg(CONF_PROFILE_NAME, "Home Assistant")
        contact = InputPhoneContact(client_id=0, phone=digits, first_name=profile_name, last_name="")
        res = await self._client.import_contacts([contact])

        users = getattr(res, "users", None) or []
        if not users:
            raise ValueError(f"Could not resolve phone number {digits}.")
        return users[0].id

    async def _ensure_client(self) -> None:
        if self._client is not None:
            return

        from pyrogram import Client
        from tgvoip_pyrogram import VoIPFileStreamService

        session_name = self._get_cfg(CONF_SESSION_NAME, "ha_telegram_voip")
        session_dir = self._get_cfg(CONF_SESSION_DIR, "/config/.telegram_voip")
        api_id = self.entry.data.get(CONF_API_ID)
        api_hash = self.entry.data.get(CONF_API_HASH)

        os.makedirs(session_dir, exist_ok=True)
        session_file = self._session_file_path()
        if not os.path.exists(session_file):
            raise RuntimeError("Telegram is not authenticated yet (missing session file).")

        # For imported sessions, api_id might be 0 (dummy) - Pyrogram will use session file values
        # For API auth, api_id/api_hash are real values from config
        self._client = Client(
            name=session_name,
            api_id=int(api_id) if api_id else 0,
            api_hash=str(api_hash) if api_hash else "",
            workdir=session_dir,
        )
        self._voip_service = VoIPFileStreamService(self._client, receive_calls=False)

    async def _wait_connected(self, timeout: float = 25.0) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline and not self._stop_event.is_set():
            st = (self._call_state_raw or "")
            if self._is_terminal_state(st):
                return False
            if any(x in st.lower() for x in ("connected", "established", "active")):
                return True
            await asyncio.sleep(0.2)
        return False

    async def _async_run_call(
        self,
        target: str,
        message: str,
        topic: Optional[str],
        language: str,
        image: Optional[str],
        ring_timeout: int,
        max_duration: int,
    ) -> None:
        try:
            # Initialize variables at method level
            original_first_name = None
            original_last_name = None
            restore_photo_path = self._get_cfg(CONF_PROFILE_PHOTO, "")
            restore_profile_name = self._get_cfg(CONF_PROFILE_NAME, "")
            
            await self._ensure_client()

            from tgvoip import VoIPServerConfig
            init_bitrate = int(self._get_cfg(CONF_INIT_BITRATE, DEFAULT_INIT_BITRATE))
            max_bitrate = int(self._get_cfg(CONF_MAX_BITRATE, DEFAULT_MAX_BITRATE))
            min_bitrate = int(self._get_cfg(CONF_MIN_BITRATE, DEFAULT_MIN_BITRATE))
            buf_size = int(self._get_cfg(CONF_BUF_SIZE, DEFAULT_BUF_SIZE))
            timeout = int(self._get_cfg(CONF_TIMEOUT, DEFAULT_TIMEOUT))
            VoIPServerConfig.set_bitrate_config(init_bitrate, max_bitrate, min_bitrate, buf_size, timeout)

            ffmpeg_path = self._get_cfg(CONF_FFMPEG_PATH, "ffmpeg")

            td = await self.hass.async_add_executor_job(self._make_tempdir)
            try:
                mp3_path = os.path.join(td, "input.mp3")
                raw_path = os.path.join(td, "input.raw")

                await self.hass.async_add_executor_job(self._tts_to_mp3, message, language, mp3_path)
                await self.hass.async_add_executor_job(self._ffmpeg_mp3_to_raw, ffmpeg_path, mp3_path, raw_path)

                _LOGGER.debug("Starting pyrogram client (start())")
                await self._client.start()

                self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_RINGING})
                resolved = await self._resolve_target(target)

                me = await self._client.get_me()
                if isinstance(resolved, int) and getattr(me, "id", None) == resolved:
                    raise ValueError("You cannot place a Telegram call to yourself.")

                # NEW CODE - Update profile name and photo with topic
                original_first_name = getattr(me, "first_name", "Home Assistant")
                original_last_name = getattr(me, "last_name", None) or ""

                if topic:
                    try:
                        # Update profile name
                        _LOGGER.info("Updating profile name from '%s %s' to '%s'", original_first_name, original_last_name, topic)
                        await self._client.update_profile(first_name=topic, last_name="")
                        
                        # Update profile photo if image parameter is provided
                        if image and os.path.exists(image):
                            await self.hass.async_add_executor_job(
                                self._set_profile_photo_sync,
                                self._client,
                                image
                            )
                            _LOGGER.info("Updated profile photo with: %s", image)      
                            
                        # Verify changes
                        me_updated = await self._client.get_me()
                        _LOGGER.info("Profile name now: '%s %s'", 
                            getattr(me_updated, "first_name", ""), 
                            getattr(me_updated, "last_name", None) or "")
                    except Exception as e:
                        _LOGGER.error("Could not update profile name/photo: %s", e, exc_info=True)

                t0 = asyncio.get_running_loop().time()
                _LOGGER.info("TGVOIP: start_call(%r) ...", resolved)
                self._call = await self._voip_service.start_call(resolved)
                _LOGGER.info("TGVOIP: start_call returned in %.3fs; call=%r", asyncio.get_running_loop().time() - t0, self._call)

                # Reset state from previous call
                self._call_state_raw = None
                self._stop_event.clear()  # ← ADD THIS TOO

                # Detach any old callbacks before attaching new ones
                try:
                    # Give old call's threads time to finish
                    await asyncio.sleep(0.2)
                except Exception:
                    pass
                    
                self._attach_call_callbacks()

                # Wait for call to connect OR fail (busy/discard/etc)
                connected = await self._wait_connected(timeout=25.0)
                if not connected:
                    # Stop quickly so "call already in progress" doesn't happen
                    raise RuntimeError(f"Call did not connect (state={self._call_state_raw})")

                out_path = os.path.join(td, "output.raw")

                size = os.path.getsize(raw_path)
                dur = size / 96000.0
                _LOGGER.info("Audio raw size=%d bytes, expected duration=%.2fs", size, dur)

                _LOGGER.info("TGVOIP: play() (executor)")
                await self.hass.async_add_executor_job(self._call.play, raw_path)
                await self.hass.async_add_executor_job(self._call.play_on_hold, [raw_path])
                await self.hass.async_add_executor_job(self._call.set_output_file, out_path)

                started = asyncio.get_running_loop().time()
                ringing_deadline = started + ring_timeout
                end_deadline = started + max_duration

                while not self._stop_event.is_set():
                    now = asyncio.get_running_loop().time()
                    if now >= end_deadline:
                        break
                    if (self.coordinator.data.get(SENSOR_CALL_STATE) == CALL_ST_RINGING and now >= ringing_deadline):
                        break
                    await asyncio.sleep(0.5)

            finally:
                await self.hass.async_add_executor_job(self._cleanup_tempdir, td)

        except ValueError as e:
            # User-facing validation errors (self-call, invalid params, etc.)
            msg = str(e)
            _LOGGER.warning("Call validation failed: %s", msg)
            self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_ERROR, SENSOR_LAST_ERROR: msg})
        except RuntimeError as e:
            # Expected call failures (timeout, declined, busy, etc.)
            msg = str(e)
            _LOGGER.warning("Call failed: %s", msg)
            self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_ERROR, SENSOR_LAST_ERROR: msg})
        except Exception as e:
            # Unexpected errors (actual bugs)
            msg = str(e)
            # Check error by module name instead of isinstance
            if "pyrogram.errors" in type(e).__module__:
                _LOGGER.warning("Telegram API error: %s", msg)
            else:
                _LOGGER.exception("Unexpected error during call: %s", msg)
            self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_ERROR, SENSOR_LAST_ERROR: msg})

        finally:
            # Restore original profile name and photo
            try:
                if topic and self._client is not None:
                    # Restore to configured profile name if set, otherwise to original
                    if restore_profile_name:
                        restore_first = restore_profile_name
                        restore_last = ""
                        _LOGGER.info("Restoring profile name to configured: '%s'", restore_first)
                    else:
                        restore_first = original_first_name
                        restore_last = original_last_name or ""
                        _LOGGER.info("Restoring profile name to original: '%s %s'", restore_first, restore_last)
                    
                    await self._client.update_profile(
                        first_name=restore_first,
                        last_name=restore_last
                    )
                    
                    # Restore original photo if configured
                    if restore_photo_path and os.path.exists(restore_photo_path):
                        await self.hass.async_add_executor_job(
                            self._set_profile_photo_sync,
                            self._client,
                            restore_photo_path
                        )
                        _LOGGER.info("Restored profile photo from: %s", restore_photo_path)
                    

                    me_restored = await self._client.get_me()
                    _LOGGER.info("Profile restored to: '%s %s'", 
                        getattr(me_restored, "first_name", ""), 
                        getattr(me_restored, "last_name", None) or "")
            except Exception as e:
                _LOGGER.error("Could not restore profile name/photo: %s", e, exc_info=True)
                
            try:
                if self._client is not None:
                    await asyncio.sleep(0.5)
                    await self._client.stop()
            except Exception:
                pass
            self._client = None
            self._voip_service = None
            self._call = None
            # self._stop_event.set()
            self._call_state_raw = None
            if self.coordinator.data.get(SENSOR_CALL_STATE) != CALL_ST_ERROR:
                self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_IDLE})

    def _attach_call_callbacks(self) -> None:
        call = self._call
        if call is None:
            return

        try:
            @call.on_call_state_changed
            def _state_changed(_call, state):
                self._call_state_raw = str(state)
                _LOGGER.info("TGVOIP: state=%s", self._call_state_raw)

                if self._is_terminal_state(self._call_state_raw):
                    self.coordinator.set_state(**{
                        SENSOR_CALL_STATE: CALL_ST_ERROR,
                        SENSOR_LAST_ERROR: f"Call ended: {self._call_state_raw}",
                    })
                    self._stop_event.set()
                    return

                st = self._call_state_raw.lower()
                if "connected" in st or "active" in st or "established" in st:
                    self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_IN_CALL})
                elif "ring" in st:
                    self.coordinator.set_state(**{SENSOR_CALL_STATE: CALL_ST_RINGING})

            @call.on_call_ended
            def _ended(_call):
                _LOGGER.info("TGVOIP: call ended callback")
                self._stop_event.set()
        except Exception:
            _LOGGER.info("TGVOIP: failed attaching callbacks")

    @staticmethod
    def _tts_to_mp3(text: str, language: str, mp3_path: str) -> None:
        from gtts import gTTS
        tts = gTTS(text, lang=language)
        tts.save(mp3_path)

    @staticmethod
    def _ffmpeg_mp3_to_raw(ffmpeg_path: str, mp3_path: str, raw_path: str) -> None:
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            mp3_path,
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-acodec",
            "pcm_s16le",
            raw_path,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    @staticmethod
    def _set_profile_photo_sync(client, photo_path: str) -> None:
        """Synchronous wrapper for set_profile_photo to avoid blocking warnings."""
        import asyncio
        
        # Pyrogram wraps methods with @sync decorator
        # We need to call it and let it handle the async execution
        # Just call it directly - the sync wrapper handles everything
        try:
            # The method is already sync-wrapped by Pyrogram, just call it
            client.set_profile_photo(photo=photo_path)
        except Exception as e:
            raise e