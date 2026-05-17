# coding=utf-8
"""
Service entry point for service.p3i.override.

Listens for playback events. On AV-start, looks for override.ini in the
playing file's folder and applies any matching settings (global + per-file
sections). Restores saved values on stop/end/error. Defers to PM4K when
script.plex.running is set on Window 10000. Skips the LAV SB setting key
if service.p3i.sb is installed (SB helper owns it).
"""
import xbmc
import xbmcgui

from . import override
from . import util
from . import verified_settings


class OverrideMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.shutdown = False

    def onAbortRequested(self):
        self.shutdown = True


class OverridePlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        # {setting_id: previous_value} for restore.
        self._saved = {}

    # ---- helpers ----------------------------------------------------------

    def _enabled(self):
        return util.get_setting_bool("auto_apply_enabled", True)

    def _safe_playing_file(self):
        try:
            return self.getPlayingFile()
        except RuntimeError:
            return None


    # ---- event handlers ---------------------------------------------------

    def onAVStarted(self):
        try:
            self._maybe_apply()
        except Exception as exc:
            util.error("onAVStarted handler crashed: {}".format(exc))

    def onPlayBackStopped(self):
        self._restore()

    def onPlayBackEnded(self):
        self._restore()

    def onPlayBackError(self):
        self._restore()

    # ---- apply / restore --------------------------------------------------

    def _maybe_apply(self):
        if not self._enabled():
            return

        # No PM4K deferral here — unlike the SB helper (which steps aside
        # because PM4K runs its own SB-toggle on the same Kodi setting), the
        # override addon doesn't conflict with PM4K. PM4K's Plex playback
        # goes through http(s) URLs that REMOTE_SCHEMES already skips, and
        # for local-file playback through PM4K the user clearly wants the
        # override they wrote to apply.

        path = self._safe_playing_file()
        if not path:
            return

        plan, sources = override.load_override_for(path)
        if not plan:
            return

        # source label for logs — list of files broadest-first, or just the
        # one path if only one file in the cascade had anything to say.
        if len(sources) == 1:
            source_label = sources[0]
        else:
            source_label = "[" + ", ".join(sources) + "]"

        # Drop SB setting key if the SB helper owns it. Two writers on the
        # same setting around the same playback event would race.
        if util.SB_SETTING_ID in plan and util.sb_helper_installed():
            util.log(
                "{}: dropping {} — {} is installed and owns this key".format(
                    source_label, util.SB_SETTING_ID, util.SB_HELPER_ADDON_ID
                )
            )
            plan = {k: v for k, v in plan.items() if k != util.SB_SETTING_ID}

        if not plan:
            return

        self._apply(plan, source_label)

    def _apply(self, plan, source):
        applied = 0
        for setting_id, raw_value in plan.items():
            coerced, ok = override.coerce_value(setting_id, raw_value)
            if not ok:
                util.warn(
                    "{}: cannot coerce {} = {!r} to setting's type, skipped".format(
                        source, setting_id, raw_value
                    )
                )
                continue

            entry = verified_settings.lookup(setting_id)
            if entry is None:
                util.warn(
                    "{}: {} is not in the verified-settings table; "
                    "mid-playback effect is not guaranteed".format(source, setting_id)
                )
            else:
                status = entry.get("status")
                if status == "lav-class":
                    util.warn(
                        "{}: {} is marked lav-class — late writes from "
                        "onAVStarted may be no-ops until the next codec "
                        "re-init".format(source, setting_id)
                    )
                elif status == "needs-restart":
                    util.warn(
                        "{}: {} is marked needs-restart — value is sampled "
                        "at stream/codec open; this write will likely affect "
                        "next playback only, not the current one".format(
                            source, setting_id
                        )
                    )
                elif status == "live-on-next-cue":
                    util.debug(
                        "{}: {} is marked live-on-next-cue — change applies "
                        "when the next subtitle line is drawn".format(
                            source, setting_id
                        )
                    )

            current = util.get_kodi_setting(setting_id)

            if current == coerced:
                # No change, but record the value so restore is symmetric in
                # case some other code path flips it during playback.
                self._saved[setting_id] = current
                util.debug("{}: {} already = {!r}, skip write".format(source, setting_id, coerced))
                continue

            if not util.set_kodi_setting(setting_id, coerced):
                util.warn(
                    "{}: failed to set {} = {!r}".format(source, setting_id, coerced)
                )
                continue

            self._saved[setting_id] = current
            util.log(
                "{}: {} {!r} -> {!r}".format(source, setting_id, current, coerced)
            )
            applied += 1

        if applied and util.get_setting_bool("show_notification", True):
            self._notify(applied, source)

    def _notify(self, count, source):
        try:
            import os
            icon = os.path.join(util.ADDON_PATH, "resources", "icon.png")
            heading = util.ADDON.getLocalizedString(32030) or "Setting override"
            msg_tpl = util.ADDON.getLocalizedString(32031) or "Applied %d override(s)"
            msg = msg_tpl % count
            # 5s to survive HDMI mode switch (~2-3s on Amlogic), matching SB helper.
            xbmcgui.Dialog().notification(heading, msg, icon, 5000, False)
        except Exception as exc:
            util.warn("notification failed: {}".format(exc))

    def _restore(self):
        if not self._saved:
            return
        for setting_id, saved_value in list(self._saved.items()):
            current = util.get_kodi_setting(setting_id)
            if current == saved_value:
                continue
            if util.set_kodi_setting(setting_id, saved_value):
                util.log("{} restored to {!r}".format(setting_id, saved_value))
            else:
                util.warn(
                    "Failed to restore {} = {!r}".format(setting_id, saved_value)
                )
        self._saved = {}


def run():
    util.log("Starting service.p3i.override")
    monitor = OverrideMonitor()
    player = OverridePlayer()

    while not monitor.abortRequested():
        if monitor.waitForAbort(10):
            break
    # Best effort: if shutdown hit mid-playback, push saved values back. If
    # nothing's pending, _restore is a no-op.
    player._restore()
    util.log("service.p3i.override stopped")
