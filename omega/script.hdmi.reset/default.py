# SPDX-License-Identifier: MIT
"""Manual Amlogic HDMI link recovery; no background service."""

import fcntl
import os
import sys
import time

PHY = "/sys/class/amhdmitx/amhdmitx0/phy"
MESSAGES = {
    30000: "p3i HDMI Reset",
    30001: "A reset is already running.",
    30002: "Amlogic HDMI PHY control is unavailable or not writable.",
    30003: "Check passed: HDMI PHY is writable. No reset performed.",
    30004: "Reset requested. Wait for the receiver and TV to reconnect.",
    30005: "Reset failed: {0}",
}


def text(message_id):
    try:
        import xbmcaddon
    except ImportError:
        return MESSAGES[message_id]
    return xbmcaddon.Addon("script.hdmi.reset").getLocalizedString(message_id) or MESSAGES[message_id]


def report(message, error=False):
    try:
        import xbmc
        import xbmcgui
    except ImportError:
        print(message, file=sys.stderr if error else sys.stdout)
        return
    xbmc.log("HDMI Reset: " + message, xbmc.LOGERROR if error else xbmc.LOGINFO)
    if "--check" not in sys.argv:
        icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
        xbmcgui.Dialog().notification(text(30000), message, icon, 3000)


def lock_path():
    try:
        import xbmcvfs
    except ImportError:
        # Installed CLI path: <Kodi home>/addons/script.hdmi.reset/default.py.
        kodi_home = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        temp = os.path.join(kodi_home, "temp")
    else:
        temp = xbmcvfs.translatePath("special://temp/")
    os.makedirs(temp, exist_ok=True)
    return os.path.join(temp, "hdmi-reset.lock")


def main():
    if not os.path.exists(PHY) or not os.access(PHY, os.W_OK):
        raise OSError(text(30002))
    if "--check" in sys.argv:
        report(text(30003))
        return

    with open(lock_path(), "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            report(text(30001))
            return
        try:
            with open(PHY, "w") as output:
                output.write("0\n")
            time.sleep(1)
        finally:
            # Attempt to restore output even if disabling or waiting raises.
            with open(PHY, "w") as output:
                output.write("1\n")
        report(text(30004))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        report(text(30005).format(error), error=True)
        raise
