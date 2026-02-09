# Telegram VoIP Calls (Home Assistant Custom Integration)

Place **Telegram VoIP calls** from Home Assistant using **text-to-speech (TTS)** and optional dynamic **profile name/photo** during the call.  
This custom integration authenticates via **Pyrogram** (either API login or importing an existing `.session` file), generates TTS audio, and streams it into a Telegram call via **tgvoip**.

[![Validate with HACS](https://img.shields.io/badge/HACS-validated-41BDF5)](https://hacs.xyz/) 
[![hassfest](https://img.shields.io/badge/hassfest-passing-brightgreen)](https://developers.home-assistant.io/docs/creating_integration_manifest/)
[![MIT License](https://img.shields.io/badge/license-MIT-informational)](LICENSE.md)

> ⚠️ This is a third‑party project, not affiliated with Telegram.

---

## ✨ Features

- Authenticate with Telegram in two ways:
  - **API ID/Hash login** (sends code to your phone, supports **2FA password**)
  - **Import an existing Pyrogram `.session` file** (already authenticated)
- Place a Telegram **VoIP call** from Home Assistant via service:
  - Generate TTS (Google TTS / `gTTS`) from a message
  - Convert audio using **FFmpeg**
  - Stream audio to the Telegram call (via `tgvoip`)
- Optional call customization:
  - **topic** (shown by sensor and can be used as temporary profile name during the call)
  - **image** path (temporary profile photo during the call)
  - Automatic **restore** of profile name/photo after call (configurable)
- Entities (sensors) per configured Telegram session:
  - Call state (`idle`, `starting`, `ringing`, `in_call`, `ending`, `error`)
  - Call topic
  - Call peer (target)
  - Last error
- Works with multiple config entries (multiple Telegram sessions).  
  Services support targeting by **device** or **sensor entity**.

---

## 🔧 Installation

### Option A — HACS (recommended)
1. Make sure you have [HACS](https://hacs.xyz/) installed in Home Assistant.
2. In Home Assistant: **HACS → Integrations → ⋮ (three dots) → Custom repositories**.  
   Add `https://github.com/Sanji78/telegram_voip` as **Category: Integration**.
3. Find **Telegram VoIP Calls** in HACS and click **Download**.
4. **Restart** Home Assistant.

### Option B — Manual
1. Copy the folder `custom_components/telegram_voip` from this repository into your Home Assistant config folder:
   - `<config>/custom_components/telegram_voip`
2. **Restart** Home Assistant.

---

## ⚙️ Configuration

1. Home Assistant → **Settings → Devices & services → Add Integration**.
2. Search for **Telegram VoIP Calls**.
3. Choose the authentication method:
   - **API ID/Hash (new authentication)**  
     Provide:
     - API ID / API Hash (from https://my.telegram.org)
     - Phone number in international format (e.g. `+393331112233`)
     - Optional default target
     - Session directory (default: `/config/.telegram_voip`)
     - Optional default profile name/photo (restored after calls via options)
   - **Import session file (already authenticated)**  
     Provide:
     - Full path to an existing `.session` file (e.g. `/config/my_session.session`)
     - Session directory where it will be stored (default: `/config/.telegram_voip`)
4. Complete verification:
   - If using API auth, enter the login code (and **2FA password** if required).
5. On success, Home Assistant will create a device and sensors for that Telegram session.

### Services

After setup, the integration exposes:

- `telegram_voip.call`  
  Places a Telegram VoIP call and plays the TTS audio.
  - **Required**: `message`
  - **Optional**: `target`, `topic`, `language`, `image`, `ring_timeout`, `max_duration`
  - Supports HA **service target** (choose device or one of the integration’s sensor entities).

- `telegram_voip.hangup`  
  Hangs up the current ringing/active call.  
  Supports HA **service target** as well.

Example service call (YAML mode in HA):
```yaml
service: telegram_voip.call
target:
  device_id: YOUR_DEVICE_ID
data:
  target: "@username"
  message: "Attention: the alarm has been triggered."
  topic: "ALARM"
  language: "en"
  image: "/config/www/alarm.jpg"
  ring_timeout: 45
  max_duration: 300
```

### Entities
For each configured Telegram session, you get sensors:
- **Call state** (`call_state`)
- **Call topic** (`call_topic`)
- **Call peer** (`call_peer`)
- **Last error** (`last_error`)

These can be used in automations, dashboards, and service targeting.

> Notes:
> - Session files are stored in the configured session directory (default: `/config/.telegram_voip`).
> - `ffmpeg` must be available in your Home Assistant environment (you can set a custom path in options).
> - The integration uses `gTTS` (Google TTS). Internet access may be required for TTS generation.

### Options (Advanced)
From the integration options you can configure:
- Default language
- FFmpeg path
- Default profile name/photo to restore after calls
- Ring timeout / max duration
- VoIP bitrate/buffer parameters (advanced tuning)

---

## 🧪 Supported versions
- Home Assistant: **2024.8** or newer (earlier may work, untested).

---

## 🐞 Troubleshooting
- Check **Settings → System → Logs** for messages under `custom_components.telegram_voip`.
- If authentication fails:
  - verify your **API ID/API Hash** on https://my.telegram.org
  - verify the phone number format is international (e.g. `+39...`)
  - if you have **2FA enabled**, you must provide the Telegram password when prompted
- If calls don’t start:
  - ensure the `.session` file exists in the session directory
  - confirm **FFmpeg** is installed and reachable (try setting `ffmpeg_path` in options)
  - ensure Home Assistant can reach the internet for `gTTS`
- If “call already in progress” appears, run `telegram_voip.hangup` and retry.

---

## 🙌 Contributing
PRs and issues are welcome. Please open an issue with logs if you hit a bug.

---

## ❤️ Donate
If this project helps you, consider buying me a coffee:  
**[PayPal](https://www.paypal.me/elenacapasso80)**.

..and yes... 😊 the paypal account is correct. Thank you so much!

---

## 📜 License
[MIT](LICENSE.md)