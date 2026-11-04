# coding=utf-8
"""
Service entry point for service.p3i.sb.

Listens for playback events. On AV-start of a movie whose IMDb or TMDB ID is in
the curated SB list, and whose audio is TrueHD or (likely) tms EAC3, set the
CoreELEC LAV seamless-branching mode. Restore the previous mode on stop / end /
error. Defers to PM4K when script.plex.running == '1' on Window 10000.
"""
import fnmatch
import os

import xbmc
import xbmcgui
import xbmcvfs

from . import util
from .sb_data import SBList

SB_MARKER_FILES = ("SB", "SB.txt")
REMOTE_SCHEMES = ("http://", "https://", "plugin://", "pvr://", "plex://", "upnp://")

LAV_SETTING_ID = "coreelec.amlogic.dolbyvision.audio.seamlessbranch"
LAV_MODE_OFF = 0

# Modes that imply LAV is actually applying SB workarounds.
ACTIVE_LAV_MODES = (4, 5)

# Codec-name prefixes reported by VideoPlayer.AudioCodec. Prefix-matched because
# Kodi returns variants like "truehd_atmos", "eac3_atmos", "eac3_joc" for
# Atmos/JOC tracks; we want to qualify all of those.
TRUEHD_PREFIXES = ("truehd",)
EAC3_PREFIXES = ("eac3", "ec3", "ec-3", "ddp", "dd+")


class SBMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.shutdown = False

    def onAbortRequested(self):
        self.shutdown = True


class SBPlayer(xbmc.Player):
    def __init__(self, sb_list):
        super().__init__()
        self.sb_list = sb_list
        self._saved_mode = None
        self._toggled = False

    # ---- helpers ----------------------------------------------------------

    def _enabled(self):
        return util.get_setting_bool("auto_switch_enabled", True)

    def _configured_mode(self):
        # 0=off, 1=seek-sync, 3=debug, 4=lav-sb (default), 5=lav-full
        return util.get_setting_int("lav_mode", 4)

    def _movie_ids(self):
        try:
            tag = self.getVideoInfoTag()
        except Exception:
            return None, None
        if not tag:
            return None, None
        imdb = None
        tmdb = None
        try:
            imdb = tag.getUniqueID("imdb") or None
        except Exception:
            pass
        try:
            tmdb = tag.getUniqueID("tmdb") or None
        except Exception:
            pass
        # Some scrapers store the IMDb id in the default field as ttNNN.
        if not imdb:
            try:
                default_id = tag.getUniqueID("") or tag.getUniqueID("unknown") or ""
            except Exception:
                default_id = ""
            if default_id.startswith("tt"):
                imdb = default_id
        return imdb, tmdb

    def _is_movie(self):
        try:
            tag = self.getVideoInfoTag()
            return tag and (tag.getMediaType() == "movie")
        except Exception:
            return False

    def _audio_codec(self):
        # Canonical Kodi infolabel for the active video player's audio codec is
        # VideoPlayer.AudioCodec (xbmc/GUIInfoManager.cpp). "Player.AudioCodec"
        # is *not* a real label and Kodi echoes the literal string back, which
        # used to make _audio_qualifies always fail.
        codec = xbmc.getInfoLabel("VideoPlayer.AudioCodec") or ""
        codec = codec.lower().strip()
        # Defensive: if Kodi echoed the label name back (contains a dot), treat
        # it as unknown rather than a real codec string.
        if "." in codec:
            return ""
        return codec

    def _audio_qualifies(self, codec):
        if not codec:
            return False
        if codec.startswith(TRUEHD_PREFIXES):
            return True
        if codec.startswith(EAC3_PREFIXES):
            # Bitrate isn't reliably available at AV-start through the public
            # API. The curated list is the gate: any EAC3 on an SB title is
            # treated as tms. False-positives only re-route through LAV.
            return True
        return False

    # ---- toggle -----------------------------------------------------------

    def _apply(self, mode):
        current = util.get_kodi_setting(LAV_SETTING_ID)
        self._saved_mode = current if isinstance(current, int) else LAV_MODE_OFF
        if self._saved_mode in ACTIVE_LAV_MODES:
            util.debug("LAV already in active mode {}, leaving as-is".format(self._saved_mode))
            self._toggled = False
            return
        ok = util.set_kodi_setting(LAV_SETTING_ID, mode)
        if ok:
            self._toggled = True
            util.log("LAV mode {} -> {}".format(self._saved_mode, mode))
            self._maybe_notify(self._saved_mode, mode)
        else:
            util.warn("Failed to set {} = {}".format(LAV_SETTING_ID, mode))
            self._toggled = False

    def _maybe_notify(self, prev, new):
        if not util.get_setting_bool("show_notification", True):
            return
        try:
            icon = os.path.join(util.ADDON_PATH, "resources", "icon.png")
            heading = util.ADDON.getLocalizedString(32030) or "Seamless branching"
            msg_tpl = util.ADDON.getLocalizedString(32031) or "LAV mode: %s -> %s"
            msg = msg_tpl % (prev, new)
            # 5s so the toast survives a HDMI mode switch (~2-3s on Amlogic).
            xbmcgui.Dialog().notification(heading, msg, icon, 5000, False)
        except Exception as exc:
            util.warn("notification failed: {}".format(exc))

    def _restore(self):
        if not self._toggled:
            return
        ok = util.set_kodi_setting(LAV_SETTING_ID, self._saved_mode)
        if ok:
            util.log("LAV mode restored to {}".format(self._saved_mode))
        else:
            util.warn("Failed to restore {} = {}".format(LAV_SETTING_ID, self._saved_mode))
        self._toggled = False
        self._saved_mode = None

    # ---- event handlers ---------------------------------------------------

    def onAVStarted(self):
        try:
            self._maybe_toggle()
        except Exception as exc:
            util.error("onAVStarted handler crashed: {}".format(exc))

    def _maybe_toggle(self):
        if not self._enabled():
            return
        if not self.isPlayingVideo():
            return
        if util.pm4k_running():
            util.debug("PM4K is running, deferring")
            return

        forced = self._has_sb_marker()
        imdb, tmdb = self._movie_ids() if self._is_movie() else (None, None)
        match = self.sb_list.match(imdb_id=imdb, tmdb_id=tmdb)
        if not match and not forced:
            return

        codec = self._audio_codec()
        if match and not forced and not self._audio_qualifies(codec):
            util.debug("SB title {} matched but audio codec {} doesn't qualify".format(
                imdb or tmdb, codec or "<none>"))
            return

        if forced:
            util.log("SB marker file present, forcing engage (codec={})".format(codec or "<none>"))
        else:
            util.log("SB match: title='{}' imdb={} tmdb={} codec={}".format(
                match.get("title", "?"), imdb, tmdb, codec))
        self._apply(self._configured_mode())

    def _has_sb_marker(self):
        """Marker semantics:
        - Empty / whitespace-only file: engage for every file in the folder
          (original behavior — preserves existing user setups).
        - Non-empty: each non-blank/non-comment line is a filename or fnmatch
          glob; engage only when the playing file's basename matches at least
          one entry. Lets a flat-library user enable SB for individual titles
          without per-folder marker scattering.
        """
        try:
            path = self.getPlayingFile()
        except RuntimeError:
            return False
        if not path:
            return False
        lower = path.lower()
        if lower.startswith(REMOTE_SCHEMES):
            return False
        folder = os.path.dirname(path)
        if not folder:
            return False
        basename = os.path.basename(path)
        for marker in SB_MARKER_FILES:
            marker_path = os.path.join(folder, marker)
            if not xbmcvfs.exists(marker_path):
                continue
            patterns = self._read_marker_patterns(marker_path)
            if patterns is None:
                # Empty / unreadable / no entries → whole-folder engage.
                return True
            if any(fnmatch.fnmatchcase(basename, p) for p in patterns):
                util.debug("SB marker {} matched {}".format(marker_path, basename))
                return True
            util.debug("SB marker {} present but no entry matched {}".format(
                marker_path, basename))
        return False

    def _read_marker_patterns(self, marker_path):
        """Returns the list of patterns from the marker file, or None if the
        file is empty / unreadable / contains nothing but blanks and comments
        (in which case the caller treats marker presence as whole-folder)."""
        try:
            f = xbmcvfs.File(marker_path)
            try:
                data = f.read()
            finally:
                f.close()
        except Exception as exc:
            util.warn("SB marker {} unreadable: {}".format(marker_path, exc))
            return None
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                util.warn("SB marker {} not UTF-8, treating as whole-folder".format(
                    marker_path))
                return None
        if not data or not data.strip():
            return None
        patterns = []
        for line in data.splitlines():
            s = line.strip()
            if not s or s[0] in ("#", ";"):
                continue
            patterns.append(s)
        return patterns or None

    def onPlayBackStopped(self):
        self._restore()

    def onPlayBackEnded(self):
        self._restore()

    def onPlayBackError(self):
        self._restore()


def run():
    util.log("Starting service.p3i.sb")
    sb_list = SBList()
    util.log("SB list has {} movies".format(len(sb_list)))

    monitor = SBMonitor()
    player = SBPlayer(sb_list)

    while not monitor.abortRequested():
        if monitor.waitForAbort(10):
            break
    # Best effort: if we were mid-restore when shutdown hit, leave the user's
    # Kodi setting in whatever state they had — restore() is idempotent.
    player._restore()
    util.log("service.p3i.sb stopped")
