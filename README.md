# Vitesy Shelfy, Natede & Eteria (Home Assistant Custom Integration)

Monitor and control your **Vitesy Shelfy, Natede & Eteria** devices from Home Assistant.  
This custom integration logs in to **Vitesy Hub** cloud, pulls device status and measurements, and exposes them as sensors and buttons in HA.

[![Validate with HACS](https://img.shields.io/badge/HACS-validated-41BDF5)](https://hacs.xyz/) 
[![hassfest](https://img.shields.io/badge/hassfest-passing-brightgreen)](https://developers.home-assistant.io/docs/creating_integration_manifest/)
[![MIT License](https://img.shields.io/badge/license-MIT-informational)](LICENSE.md)

> ⚠️ This is a third‑party project, not affiliated with Vitesy.

---

## ✨ Features

- Login with your **Vitesy** account (email + password).
- Pulls devices from the Vitesy Hub API and updates **every minute**.
- Sensors for:
  - Battery level and charging
  - Wi‑Fi SSID, connection state, model, firmware
  - Fridge temperature (`TMP01-SY`), door opens (`DOC-SY`), open seconds (`DOT-SY`)
  - Air quality **score** (as percent) and **last update** timestamp
  - Active **program** (name, description, icon, fan, power)
  - Maintenance dates for **filter** and **fridge**, plus remaining days
- Buttons to **Reset filter** and **Reset fridge** maintenance counters.

---

## 🔧 Installation

### Option A — HACS (recommended)
1. Make sure you have [HACS](https://hacs.xyz/) installed in Home Assistant.
2. In Home Assistant: **HACS → Integrations → ⋮ (three dots) → Custom repositories**.  
   Add `https://github.com/Sanji78/vitesy_shelfy` as **Category: Integration**.
3. Find **Vitesy Shelfy, Natede & Eteria** in HACS and click **Download**.
4. **Restart** Home Assistant.

### Option B — Manual
1. Copy the folder `custom_components/vitesy_shelfy` from this repository into your Home Assistant config folder:
   - `<config>/custom_components/vitesy_shelfy`
2. **Restart** Home Assistant.

---

## ⚙️ Configuration

1. Home Assistant → **Settings → Devices & services → Add Integration**.
2. Search for **Vitesy Shelfy, Natede & Eteria**.
3. Enter your **Vitesy email and password**.
4. On success, entities will be created for each device.

### Entities
- **Sensors**: battery, charging, Wi‑Fi SSID, connection status, model, firmware, temperature, door opens, open seconds, air quality score, timestamps, program info, maintenance dates and remaining days.
- **Buttons**: *Filter Washed*, *Fridge Washed* (call Vitesy APIs to reset maintenance).

> Notes:
> - Credentials are stored in Home Assistant’s config entries.
> - The integration communicates with Vitesy’s cloud API (internet required).

---

## 🧪 Supported versions
- Home Assistant: **2024.8** or newer (earlier may work, untested).

---

## 🐞 Troubleshooting
- Check **Settings → System → Logs** for messages under `custom_components.vitesy_shelfy`.
- If login fails, verify email/password by signing into the official Vitesy app.
- If entities don’t update, ensure Home Assistant can reach the internet.

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
