DOMAIN = "telegram_voip"

CONF_API_ID = "api_id"
CONF_API_HASH = "api_hash"
CONF_SESSION_NAME = "session_name"
CONF_SESSION_DIR = "session_dir"

CONF_DEFAULT_TARGET = "default_target"
CONF_DEFAULT_LANGUAGE = "default_language"
CONF_FFMPEG_PATH = "ffmpeg_path"
CONF_PROFILE_PHOTO = "profile_photo"
CONF_PROFILE_NAME = "profile_name"

CONF_RING_TIMEOUT = "ring_timeout"
CONF_MAX_DURATION = "max_duration"

# VoIP bitrate config (mirrors your set_bitrate_config usage)
CONF_INIT_BITRATE = "init_bitrate"
CONF_MAX_BITRATE = "max_bitrate"
CONF_MIN_BITRATE = "min_bitrate"
CONF_BUF_SIZE = "buf_size"
CONF_TIMEOUT = "timeout"

LANG_EN = "en"
LANG_IT = "it"
LANG_ES = "es"
LANG_FR = "fr"
LANG_DE = "de"
LANG_PT = "pt"
LANG_ZH = "zh"
LANG_JA = "ja"
SUPPORTED_LANGUAGES = [LANG_EN, LANG_IT, LANG_ES, LANG_FR, LANG_DE, LANG_PT, LANG_ZH, LANG_JA]

DEFAULT_SESSION_NAME = "ha_telegram_voip"
DEFAULT_SESSION_DIR = "/config/.telegram_voip"  # must be persisted by HA volume
DEFAULT_LANGUAGE = LANG_IT
DEFAULT_RING_TIMEOUT = 45
DEFAULT_MAX_DURATION = 300

DEFAULT_INIT_BITRATE = 80000
DEFAULT_MAX_BITRATE = 100000
DEFAULT_MIN_BITRATE = 60000
DEFAULT_BUF_SIZE = 5000
DEFAULT_TIMEOUT = 5000

# Sensors
SENSOR_CALL_STATE = "call_state"
SENSOR_CALL_TOPIC = "call_topic"
SENSOR_CALL_PEER = "call_peer"
SENSOR_LAST_ERROR = "last_error"

CALL_ST_IDLE = "idle"
CALL_ST_STARTING = "starting"
CALL_ST_RINGING = "ringing"
CALL_ST_IN_CALL = "in_call"
CALL_ST_ENDING = "ending"
CALL_ST_ERROR = "error"

CONF_PHONE = "phone"
CONF_2FA_PASSWORD = "password"