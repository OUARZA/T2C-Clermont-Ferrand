"""Constants for T2C Clermont-Ferrand."""

DOMAIN = "t2c_clermontferrand"

DATASET_API_URL = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "syndicat-mixte-des-transports-en-commun-de-lagglomeration-clermontoise-"
    "smtc-ac-reseau-t2c-gtfs-gtfs-rt/"
)
GTFS_RT_TRIP_UPDATES_URL = (
    "https://proxy.transport.data.gouv.fr/resource/"
    "t2c-clermont-gtfs-rt-trip-update"
    "?token=xdgqKBTAzhw4DSPz6zeGc4c5eW0LhwztcGv4-vpzP4U"
)

CONF_LINE_NAME = "line_name"
CONF_LINE_ID = "line_id"
CONF_DIRECTION_NAME = "direction_name"
CONF_DIRECTION_ID = "direction_id"
CONF_STOP_NAME = "stop_name"
CONF_STOP_ID = "stop_id"

DEFAULT_SCAN_INTERVAL_MINUTES = 1
DEFAULT_DEPARTURE_LIMIT = 5

ATTR_LINE = "line"
ATTR_DIRECTION = "direction"
ATTR_STOP = "stop"
ATTR_NEXT_PASSAGES = "next_passages"
ATTR_RAW_PASSAGES = "raw_passages"
ATTR_DESTINATION = "destination"
ATTR_REALTIME = "realtime"
ATTR_DUE_AT = "due_at"
