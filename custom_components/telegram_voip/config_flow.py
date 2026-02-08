from __future__ import annotations

import os
import shutil
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_API_ID,
    CONF_API_HASH,
    CONF_DEFAULT_TARGET,
    CONF_SESSION_NAME,
    CONF_SESSION_DIR,
    DEFAULT_SESSION_DIR,
    DEFAULT_SESSION_NAME,
    CONF_PHONE,
    CONF_2FA_PASSWORD,
    CONF_PROFILE_PHOTO,
    CONF_PROFILE_NAME,
)

AUTH_METHOD_API = "api"
AUTH_METHOD_SESSION = "session_file"

STEP_AUTH_METHOD_SCHEMA = vol.Schema({
    vol.Required("auth_method", default=AUTH_METHOD_API): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value="api", label="api"),
                selector.SelectOptionDict(value="session_file", label="session_file"),
            ],
            mode=selector.SelectSelectorMode.LIST,
            translation_key="auth_method",
        )
    )
})

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): int,
        vol.Required(CONF_API_HASH): str,
        vol.Required(CONF_PHONE): str,
        vol.Optional(CONF_DEFAULT_TARGET, default=""): str,
        # vol.Optional(CONF_SESSION_NAME, default=DEFAULT_SESSION_NAME): str,
        vol.Optional(CONF_SESSION_DIR, default=DEFAULT_SESSION_DIR): str,
        vol.Optional(CONF_PROFILE_PHOTO, default=""): str,
        vol.Optional(CONF_PROFILE_NAME, default=""): str,
    }
)

STEP_SESSION_IMPORT_SCHEMA = vol.Schema({
    vol.Required("session_file_path"): str,
    vol.Optional(CONF_DEFAULT_TARGET, default=""): str,
    vol.Optional(CONF_SESSION_DIR, default=DEFAULT_SESSION_DIR): str,
    vol.Optional(CONF_PROFILE_PHOTO, default=""): str,
    vol.Optional(CONF_PROFILE_NAME, default=""): str,
})

STEP_CODE_SCHEMA = vol.Schema({vol.Required("code"): str})

STEP_PASSWORD_SCHEMA = vol.Schema({vol.Required(CONF_2FA_PASSWORD): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._user_input = None
        self._client = None
        self._phone_code_hash = None
        self._auth_method = None

    async def async_step_user(self, user_input=None):
        """Handle authentication method selection."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_AUTH_METHOD_SCHEMA)

        self._auth_method = user_input["auth_method"]

        if self._auth_method == AUTH_METHOD_API:
            return await self.async_step_api_auth()
        else:
            return await self.async_step_session_import()

    async def async_step_api_auth(self, user_input=None):
        """Handle API-based authentication."""
        if user_input is None:
            return self.async_show_form(step_id="api_auth", data_schema=STEP_USER_DATA_SCHEMA)

        self._user_input = user_input

        session_dir = user_input[CONF_SESSION_DIR]
        session_name = DEFAULT_SESSION_NAME#user_input[CONF_SESSION_NAME]
        await self.hass.async_add_executor_job(lambda: os.makedirs(session_dir, exist_ok=True))

        from pyrogram import Client

        self._client = Client(
            name=session_name,
            api_id=int(user_input[CONF_API_ID]),
            api_hash=str(user_input[CONF_API_HASH]),
            workdir=session_dir,
        )

        await self._client.connect()

        # Send login code
        sent = await self._client.send_code(user_input[CONF_PHONE])
        self._phone_code_hash = sent.phone_code_hash

        return self.async_show_form(step_id="code", data_schema=STEP_CODE_SCHEMA)

    async def async_step_session_import(self, user_input=None):
        """Handle session file import."""
        if user_input is None:
            return self.async_show_form(
                step_id="session_import",
                data_schema=STEP_SESSION_IMPORT_SCHEMA,
                description_placeholders={
                    "info": "Provide the full path to an existing Pyrogram .session file (e.g., /config/my_session.session)"
                }
            )

        session_file_path = user_input["session_file_path"]
        session_dir = user_input[CONF_SESSION_DIR]

        # Validate session file exists
        if not os.path.exists(session_file_path):
            return self.async_show_form(
                step_id="session_import",
                data_schema=STEP_SESSION_IMPORT_SCHEMA,
                errors={"base": "session_file_not_found"}
            )

        await self.hass.async_add_executor_job(lambda: os.makedirs(session_dir, exist_ok=True))

        # Load session to get username
        from pyrogram import Client

        # Temporarily connect to get user info
        temp_name = "temp_session_check"
        temp_session_path = os.path.join(session_dir, f"{temp_name}.session")
        
        # Copy session file temporarily
        await self.hass.async_add_executor_job(shutil.copy2, session_file_path, temp_session_path)

        try:
            temp_client = Client(name=temp_name, workdir=session_dir)
            await temp_client.connect()
            
            # Get authenticated user info
            me = await temp_client.get_me()
            username = me.username if me.username else f"user_{me.id}"
            
            await temp_client.disconnect()
            
            # Remove temp file
            await self.hass.async_add_executor_job(os.remove, temp_session_path)

        except Exception as e:
            # Clean up temp file
            if os.path.exists(temp_session_path):
                await self.hass.async_add_executor_job(os.remove, temp_session_path)
            
            return self.async_show_form(
                step_id="session_import",
                data_schema=STEP_SESSION_IMPORT_SCHEMA,
                errors={"base": "invalid_session_file"}
            )

        # Copy session with proper name
        final_session_name = f"{username}"
        final_session_path = os.path.join(session_dir, f"{final_session_name}.session")
        await self.hass.async_add_executor_job(os.rename, session_file_path, final_session_path)

        # Store configuration
        await self.async_set_unique_id(f"{DOMAIN}_{final_session_name}")
        self._abort_if_unique_id_configured()

        profile_photo = user_input.get(CONF_PROFILE_PHOTO, "")
        profile_name = user_input.get(CONF_PROFILE_NAME, "")

        return self.async_create_entry(
            title=f"Telegram VoIP ({username})",
            data={
                CONF_SESSION_NAME: final_session_name,
                CONF_SESSION_DIR: session_dir,
                CONF_DEFAULT_TARGET: user_input.get(CONF_DEFAULT_TARGET, ""),
                CONF_API_ID: 0,
                CONF_API_HASH: "",               
            },
            options={
                CONF_PROFILE_PHOTO: profile_photo,
                CONF_PROFILE_NAME: profile_name,
            },
        )

    async def async_step_code(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="code", data_schema=STEP_CODE_SCHEMA)

        code = user_input["code"]

        try:
            await self._client.sign_in(
                phone_number=self._user_input[CONF_PHONE],
                phone_code_hash=self._phone_code_hash,
                phone_code=code,
            )
        except Exception as e:
            msg = str(e).lower()
            # If 2FA is enabled, Telegram requires a password
            if "password" in msg or "sessionpasswordneeded" in msg:
                return self.async_show_form(step_id="password", data_schema=STEP_PASSWORD_SCHEMA)
            return self.async_show_form(
                step_id="code",
                data_schema=STEP_CODE_SCHEMA,
                errors={"base": "invalid_code"},
            )

        return await self._finish()

    async def async_step_password(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="password", data_schema=STEP_PASSWORD_SCHEMA)

        try:
            await self._client.check_password(user_input[CONF_2FA_PASSWORD])
        except Exception:
            return self.async_show_form(
                step_id="password",
                data_schema=STEP_PASSWORD_SCHEMA,
                errors={"base": "invalid_password"},
            )

        return await self._finish()

    async def _finish(self):
        """Finish API authentication and rename session with username."""
        try:
            # Get user info before disconnecting
            me = await self._client.get_me()
            username = me.username if me.username else f"user_{me.id}"
            
            await self._client.disconnect()
        except Exception:
            await self._client.disconnect()
            username = "telegram_user"

        # Rename session file to username
        session_dir = self._user_input[CONF_SESSION_DIR]
        old_session_name = DEFAULT_SESSION_NAME #self._user_input[CONF_SESSION_NAME]
        new_session_name = username
        
        old_session_path = os.path.join(session_dir, f"{old_session_name}.session")
        new_session_path = os.path.join(session_dir, f"{new_session_name}.session")
        
        if os.path.exists(old_session_path):
            await self.hass.async_add_executor_job(os.rename, old_session_path, new_session_path)

        await self.async_set_unique_id(f"{DOMAIN}_{new_session_name}")
        self._abort_if_unique_id_configured()

        # Store everything except password
        data = dict(self._user_input)
        data.pop(CONF_2FA_PASSWORD, None)
        data[CONF_SESSION_NAME] = new_session_name  # Use new name
        
        # Extract profile settings for options
        profile_photo = data.pop(CONF_PROFILE_PHOTO, "")
        profile_name = data.pop(CONF_PROFILE_NAME, "")

        return self.async_create_entry(
            title=f"Telegram VoIP (@{username})",
            data=data,
            options={
                CONF_PROFILE_PHOTO: profile_photo,
                CONF_PROFILE_NAME: profile_name,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        from .const import (
            CONF_DEFAULT_LANGUAGE,
            CONF_FFMPEG_PATH,
            CONF_PROFILE_PHOTO,
            CONF_PROFILE_NAME,
            CONF_RING_TIMEOUT,
            CONF_MAX_DURATION,
            CONF_INIT_BITRATE,
            CONF_MAX_BITRATE,
            CONF_MIN_BITRATE,
            CONF_BUF_SIZE,
            CONF_TIMEOUT,
            DEFAULT_LANGUAGE,
            DEFAULT_RING_TIMEOUT,
            DEFAULT_MAX_DURATION,
            DEFAULT_INIT_BITRATE,
            DEFAULT_MAX_BITRATE,
            DEFAULT_MIN_BITRATE,
            DEFAULT_BUF_SIZE,
            DEFAULT_TIMEOUT,
            SUPPORTED_LANGUAGES,
        )

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional(CONF_DEFAULT_LANGUAGE, default=self.entry.options.get(CONF_DEFAULT_LANGUAGE, DEFAULT_LANGUAGE)): vol.In(SUPPORTED_LANGUAGES),
                    vol.Optional(CONF_FFMPEG_PATH, default=self.entry.options.get(CONF_FFMPEG_PATH, "ffmpeg")): str,
                    vol.Optional(CONF_PROFILE_PHOTO, default=self.entry.options.get(CONF_PROFILE_PHOTO, "")): str,
                    vol.Optional(CONF_PROFILE_NAME, default=self.entry.options.get(CONF_PROFILE_NAME, "")): str,
                    vol.Optional(CONF_RING_TIMEOUT, default=self.entry.options.get(CONF_RING_TIMEOUT, DEFAULT_RING_TIMEOUT)): int,
                    vol.Optional(CONF_MAX_DURATION, default=self.entry.options.get(CONF_MAX_DURATION, DEFAULT_MAX_DURATION)): int,
                    vol.Optional(CONF_INIT_BITRATE, default=self.entry.options.get(CONF_INIT_BITRATE, DEFAULT_INIT_BITRATE)): int,
                    vol.Optional(CONF_MAX_BITRATE, default=self.entry.options.get(CONF_MAX_BITRATE, DEFAULT_MAX_BITRATE)): int,
                    vol.Optional(CONF_MIN_BITRATE, default=self.entry.options.get(CONF_MIN_BITRATE, DEFAULT_MIN_BITRATE)): int,
                    vol.Optional(CONF_BUF_SIZE, default=self.entry.options.get(CONF_BUF_SIZE, DEFAULT_BUF_SIZE)): int,
                    vol.Optional(CONF_TIMEOUT, default=self.entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)): int,
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema)

        return self.async_create_entry(title="", data=user_input)