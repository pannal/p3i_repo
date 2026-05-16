# coding=utf-8
import json
import os

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))

LOG_PREFIX = "service.p3i.sb"


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[{}] {}".format(LOG_PREFIX, msg), level)


def debug(msg):
    log(msg, xbmc.LOGDEBUG)


def warn(msg):
    log(msg, xbmc.LOGWARNING)


def error(msg):
    log(msg, xbmc.LOGERROR)


def get_setting_bool(key, default=False):
    try:
        return ADDON.getSettingBool(key)
    except Exception:
        v = ADDON.getSetting(key)
        if v in ("true", "True", "1"):
            return True
        if v in ("false", "False", "0", ""):
            return False
        return default


def get_setting_int(key, default=0):
    try:
        return ADDON.getSettingInt(key)
    except Exception:
        v = ADDON.getSetting(key)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default


def pm4k_running():
    """True if PlexMod4Kodi (script.plexmod) is the active session."""
    return xbmc.getInfoLabel("Window(10000).Property(script.plex.running)") == "1"


def read_json(path):
    if not xbmcvfs.exists(path):
        return None
    f = xbmcvfs.File(path)
    try:
        data = f.read()
    finally:
        f.close()
    try:
        return json.loads(data)
    except ValueError as exc:
        error("Failed to parse JSON at {}: {}".format(path, exc))
        return None


def jsonrpc(method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        req["params"] = params
    raw = xbmc.executeJSONRPC(json.dumps(req))
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def get_kodi_setting(setting_id):
    resp = jsonrpc("Settings.GetSettingValue", {"setting": setting_id})
    return resp.get("result", {}).get("value")


def set_kodi_setting(setting_id, value):
    resp = jsonrpc("Settings.SetSettingValue", {"setting": setting_id, "value": value})
    return resp.get("result") is True
