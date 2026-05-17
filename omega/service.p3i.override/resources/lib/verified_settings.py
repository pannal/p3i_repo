# coding=utf-8
"""
Catalog of Kodi settings that have been explicitly verified to take effect
mid-playback when written via override.ini.

A setting is "verified" when:
- The C++ side reacts to mid-playback writes (OnSettingChanged callback +
  atomic-cached value, or live re-push to sysfs), AND
- It's been tested in this project.

Settings not in this table can still be written via override.ini — the
addon emits a warning but writes them anyway. Whether they take effect
mid-playback depends on whether the C++ consumer caches the value at
codec/stream open. The :status: field documents what we know:

  "live"             — OnSettingChanged + atomic, value picked up per-packet
                       or per-frame. Late writes from onAVStarted are fine.
  "live-via-sysfs"   — Setting drives a sysfs flag; the change handler
                       re-pushes the sysfs on every write. Live after the
                       corresponding C++ patch lands.
  "live-on-next-cue" — Value is cached in a render-time style struct, but
                       an observer fires on settings change and the next
                       drawn subtitle picks it up. Applies within one cue
                       (typically <1s for dense dialogue, longer for sparse
                       subs). Useful in practice; not instant.
  "lav-class"        — Sampled once at codec/stream open and cached. Needs a
                       C++ patch (see xbmc commit 72daca6f5a for the LAV
                       pattern) before late writes take effect.
  "needs-restart"    — Sampled at codec/stream/demuxer open or app startup
                       and never re-read. Mid-playback write may apply to
                       the next playback but not the current one. Document
                       and warn; the addon writes anyway in case the user
                       wants it set going forward.

Keep this list in sync with SETTINGS.md and the C++ side (xbmc tree).
"""

VERIFIED = {
    # ------- DV: dynamic bitstream-converter knobs -------
    "coreelec.amlogic.dolbyvision.cmv40.append": {
        "status": "live",
        "type": "int",
        "values": "0=off, 1=CMv2.9 without L2 trims, 2=always",
        "notes": (
            "Atomic-cached in CDVDVideoCodecAmlogic; applied per-packet from "
            "AddData() via ApplyDynamicDoViSettings(). WRITABLE ONLY WHEN: "
            "DV type = Display-LED (0), no VP override (video.processor = 0), "
            "and DV mode != 2 — these are visible-dependencies on the setting. "
            "On other paths Kodi rejects the JSON-RPC write with InvalidParams "
            "(the addon logs this) and the codec also zeroes the value, since "
            "CMv4.0 append only matters when the TV does the tonemapping. "
            "If your override fails on a Player-LED / LLDV / VS10 setup this "
            "is the reason — set DV type to Display-LED, or scope the override "
            "to titles played in that mode."
        ),
    },
    "coreelec.amlogic.dolbyvision.level5.override": {
        "status": "live",
        "type": "string",
        "format": "top,bottom,left,right (unsigned ints in RPU active-area space) or empty",
        "notes": (
            "L5 active-area override. Substituted into doviFrame/StreamMetadata "
            "during RPU parse so the overlay-active-area calc uses these offsets "
            "instead of the stream's. When set, also stops the active-area auto-"
            "detect path (would just burn background cycles, since CalcOverlayActiveArea "
            "picks override over detect). NOTE: this affects Kodi-side overlay "
            "and DataCacheCore consumers only — the emitted RPU still carries "
            "the stream's original L5, so the TV's tonemapping sees the original values."
        ),
    },

    # ------- DV: L5 enable surfaces (sysfs-driven) -------
    "coreelec.amlogic.dolbyvision.level5": {
        "status": "live-via-sysfs",
        "type": "bool",
        "notes": "Master L5 enable. aml_dv_apply_l5_sysfs re-pushed on change.",
    },
    "coreelec.amlogic.dolbyvision.std.source.metadata.level5": {
        "status": "live-via-sysfs",
        "type": "bool",
        "notes": "Forward source L5 metadata to the DV pipeline. Live-via-sysfs.",
    },
    "coreelec.amlogic.dolbyvision.std.source.metadata.level5.osdst": {
        "status": "live-via-sysfs",
        "type": "bool",
        "notes": "L5 OSD-start signaling. Live-via-sysfs.",
    },
    "coreelec.amlogic.dolbyvision.level5.signal.subs": {
        "status": "live-via-sysfs",
        "type": "int",
        "notes": "L5 subtitle signaling mode. Live-via-sysfs.",
    },
    "coreelec.amlogic.dolbyvision.detect.active.area": {
        "status": "live-via-sysfs",
        "type": "bool",
        "notes": "L5 active-area auto-detect. Live-via-sysfs.",
    },

    # ------- Audio: LAV seamless-branching -------
    "coreelec.amlogic.dolbyvision.audio.seamlessbranch": {
        "status": "live",
        "type": "int",
        "values": "0=off, 1=seek-sync, 3=debug, 4=LAV SB, 5=LAV full",
        "notes": (
            "Made live by xbmc commit 72daca6f5a — re-reads on codec Open() "
            "and reacts to OnSettingChanged. NOTE: if service.p3i.sb is "
            "installed, override.ini writes to this key are skipped (SB helper "
            "owns the key)."
        ),
    },

    # ------- Subtitles: PGS HDR-to-SDR shader params (per-frame live) -------
    "subtitles.pgshdrtosdr.brightness": {
        "status": "live",
        "notes": "Fed per-frame to the PGS HDR-to-SDR shader as m_pqRefNits.",
    },
    "subtitles.pgshdrtosdr.saturation": {
        "status": "live",
        "notes": "Fed per-frame to the PGS HDR-to-SDR shader as m_pqSaturation.",
    },
    "subtitles.pgshdrtosdr.tonemap": {
        "status": "live",
        "notes": "Per-frame: selects the shader tone-mapping pipeline.",
    },
    "subtitles.pgshdrtosdr.mode": {
        "status": "live",
        "values": "Classic / Linear / Luma (see memory pgs-hdr-color-fix)",
        "notes": "Per-frame: selects the tonemapping algorithm in the shader.",
    },

    # ------- Subtitles: other render-time live settings -------
    "subtitles.captionsalign": {
        "status": "live",
        "notes": "Read per-frame in ConvertLibass via rOpts.horizontalAlignment.",
    },
    "subtitles.stereoscopicdepth": {
        "status": "live",
        "notes": "Read per-frame in GetStereoscopicDepth() for the 3D offset.",
    },
    "subtitles.bitmapzoom": {
        "status": "live",
        "notes": "Read per-frame for bitmap scale + GPU texture filter.",
    },

    # ------- Subtitles: style (cached in m_overlayStyle, applies on next cue) -------
    "subtitles.fontname": {
        "status": "live-on-next-cue",
        "notes": "Baked into ASS style at first render; SubtitlesSettings observer triggers re-cache so the next drawn subtitle picks it up.",
    },
    "subtitles.fontsize": {
        "status": "live-on-next-cue",
        "notes": "Baked into ASS style with playResY scaling. Observer-refreshed.",
    },
    "subtitles.style": {
        "status": "live-on-next-cue",
        "notes": "Font bold/italic. Observer-refreshed.",
    },
    "subtitles.colorpick": {
        "status": "live-on-next-cue",
        "notes": "Font colour. Observer-refreshed; applies on next subtitle cue.",
    },
    "subtitles.bordersize": {
        "status": "live-on-next-cue",
        "notes": "ASS Outline. Observer-refreshed.",
    },
    "subtitles.bordercolorpick": {
        "status": "live-on-next-cue",
        "notes": "ASS OutlineColour. Observer-refreshed.",
    },
    "subtitles.opacity": {
        "status": "live-on-next-cue",
        "notes": "Font opacity. Observer-refreshed.",
    },
    "subtitles.blur": {
        "status": "live-on-next-cue",
        "notes": "Blur. Observer-refreshed.",
    },
    "subtitles.backgroundtype": {
        "status": "live-on-next-cue",
        "notes": "ASS borderStyle (outline / box). Observer-refreshed.",
    },
    "subtitles.shadowcolor": {
        "status": "live-on-next-cue",
        "notes": "ASS BackColour (shadow). Observer-refreshed.",
    },
    "subtitles.shadowopacity": {
        "status": "live-on-next-cue",
        "notes": "Shadow opacity. Observer-refreshed.",
    },
    "subtitles.shadowsize": {
        "status": "live-on-next-cue",
        "notes": "ASS Shadow. Observer-refreshed.",
    },
    "subtitles.bgcolorpick": {
        "status": "live-on-next-cue",
        "notes": "Background colour. Observer-refreshed.",
    },
    "subtitles.bgopacity": {
        "status": "live-on-next-cue",
        "notes": "Background opacity. Observer-refreshed.",
    },
    "subtitles.marginvertical": {
        "status": "live-on-next-cue",
        "notes": (
            "Vertical margin. Observer-refreshed. NOTE: source-level comment "
            "warns that mid-playback changes cause seek artifacts — prefer "
            "setting at start of playback rather than toggling during."
        ),
    },
    "subtitles.align": {
        "status": "live-on-next-cue",
        "notes": "ASS alignment. Observer-refreshed.",
    },
    "subtitles.overridefonts": {
        "status": "live-on-next-cue",
        "notes": "Whether to override ASS-embedded fonts. Observer-refreshed.",
    },
    "subtitles.overridestyles": {
        "status": "live-on-next-cue",
        "notes": "Override ASS style enum. Observer-refreshed.",
    },
    "subtitles.overrideass": {
        "status": "live-on-next-cue",
        "notes": "Whether to apply override flags. Observer-refreshed.",
    },

    # ------- Subtitles: needs-restart (sampled at stream/codec open) -------
    "subtitles.pgshdrtosdr": {
        "status": "needs-restart",
        "notes": (
            "Master PGS HDR-to-SDR enable. Sampled at PGS codec open in "
            "DVDOverlayCodecFFmpeg; mid-playback toggle won't reopen. Set "
            "globally; tune the brightness/saturation/tonemap/mode params "
            "per folder instead."
        ),
    },
    "subtitles.charset": {
        "status": "needs-restart",
        "notes": "Applied to libass at subtitle-stream Configure(); mid-playback change won't reconfigure.",
    },
    "subtitles.parsecaptions": {
        "status": "needs-restart",
        "notes": "Sampled during demux setup. Mid-playback toggle won't take effect.",
    },
    "locale.subtitlelanguage": {
        "status": "needs-restart",
        "notes": "Read at subtitle-stream selection time. Mid-playback change won't reselect the active subtitle track.",
    },
}


def is_verified(setting_id):
    return setting_id in VERIFIED


def lookup(setting_id):
    return VERIFIED.get(setting_id)
