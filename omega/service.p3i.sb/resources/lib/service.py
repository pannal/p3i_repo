# coding=utf-8
"""
Service entry point for service.p3i.sb.

Listens for playback events. On AV-start of a movie whose IMDb or TMDB ID is in
the curated SB list, and whose audio is TrueHD or (likely) tms EAC3, set the
CoreELEC LAV seamless-branching mode. Restore the previous mode on stop / end /
error. Defers to PM4K when script.plex.running == '1' on Window 10000.
"""
import xbmc

from . import util
from .sb_data import SBList

LAV_SETTING_ID = "coreelec.amlogic.dolbyvision.audio.seamlessbranch"
LAV_MODE_OFF = 0

# Modes that imply LAV is actually applying SB workarounds.
ACTIVE_LAV_MODES = (4, 5)

# Audio codec strings reported by Kodi's Player.getAudioStream / VideoInfoTag.
TRUEHD_CODECS = ("truehd",)
EAC3_CODECS = ("eac3", "ec3", "ddp", "dd+", "eac-3")


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
        # getAudioStream returns the currently selected index; details via JSON-RPC.
        # Use Player.getAvailableAudioStreams + getAudioStream() index, then look
        # at the codec through xbmc.getInfoLabel which gives us the active codec
        # without needing the JSON-RPC Player.GetProperties round-trip.
        codec = xbmc.getInfoLabel("Player.AudioCodec") or ""
        return codec.lower().strip()

    def _audio_qualifies(self, codec):
        if not codec:
            return False
        if codec in TRUEHD_CODECS:
            return True
        if codec in EAC3_CODECS:
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
        else:
            util.warn("Failed to set {} = {}".format(LAV_SETTING_ID, mode))
            self._toggled = False

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
        if util.pm4k_running():
            util.debug("PM4K is running, deferring")
            return
        if not self._is_movie():
            return
        imdb, tmdb = self._movie_ids()
        match = self.sb_list.match(imdb_id=imdb, tmdb_id=tmdb)
        if not match:
            return
        codec = self._audio_codec()
        if not self._audio_qualifies(codec):
            util.debug("SB title {} matched but audio codec {} doesn't qualify".format(
                imdb or tmdb, codec or "<none>"))
            return
        util.log("SB match: title='{}' imdb={} tmdb={} codec={}".format(
            match.get("title", "?"), imdb, tmdb, codec))
        self._apply(self._configured_mode())

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
