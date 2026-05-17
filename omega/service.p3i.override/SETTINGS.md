# override.ini reference

`service.p3i.override` watches for playback and applies per-folder Kodi
setting overrides from an `override.ini` file next to the playing file.

## File location and walk

`override.ini` is read from the playing file's folder **and** one parent
folder, so a library-wide tweak doesn't need a copy in every subfolder.
Standard layouts:

| Layout | File folder | Parent (also walked) |
| --- | --- | --- |
| Movie in per-title subfolder | `/Movies/Title/` | `/Movies/` |
| Movie in flat library        | `/Movies/`      | (root — usually no `override.ini` there) |
| TV episode                   | `/TV/Show/Season 01/` | `/TV/Show/` |

Cascade is **broadest-first**: the parent folder's `override.ini` applies
first, then the file folder's, with narrower overriding broader per key.
Same precedence model as `[<filename>]` sections inside a single file —
outermost sets the default, innermost wins the override.

For per-episode-subfolder layouts (`/TV/Show/Season 01/S01E03/episode.mkv`),
the walk reaches the season folder but not the show folder; put that level
of override.ini at the season folder instead, or skip the per-episode
subfolders.

## File format

```ini
# Comments with '#' or ';' (full-line only).

# Keys before any section are treated as implicit [global].
# A folder with one movie can just use:
coreelec.amlogic.dolbyvision.cmv40.append = 2

# Or with explicit sections — useful for a flat library folder or a TV
# season folder:

[global]
coreelec.amlogic.dolbyvision.cmv40.append = 2

[Avatar (2009).mkv]
coreelec.amlogic.dolbyvision.level5.override = 140,140,0,0

# fnmatch globs are supported in section names:
[Avatar*.mkv]
coreelec.amlogic.dolbyvision.cmv40.append = 1
```

### Apply order

1. `[global]` (and implicit-global keys above any section) — always applied.
2. Each named section whose name fnmatches the playing file's basename —
   applied in declaration order; later sections override earlier ones for
   the same key.

Filename matching is case-sensitive (Linux filesystem semantics).

### Value coercion

Values are coerced to the setting's existing type by probing
`Settings.GetSettingValue` first:

| Setting type | Accepted INI form |
| --- | --- |
| bool   | `true` / `false` / `yes` / `no` / `on` / `off` / `1` / `0` |
| int    | integer literal |
| float  | decimal literal |
| string | passed through verbatim (e.g., the L5 override format) |

A coercion failure is logged and the entry is skipped.

## Examples

### One movie per folder — single tweak

`/Movies/Avatar (2009)/override.ini`:
```ini
# Force CMv4.0 append for any title in this folder.
coreelec.amlogic.dolbyvision.cmv40.append = 2
```

### Flat library — per-file tuning with a global default

`/Movies/override.ini`:
```ini
[global]
coreelec.amlogic.dolbyvision.cmv40.append = 2

[Avatar (2009).mkv]
# 1080p 2.35:1 letterbox — fill in L5 the stream omitted so subtitles ride above the bar
coreelec.amlogic.dolbyvision.level5.override = 140,140,0,0

[Dune (2021).mkv]
# 4K 2.4:1
coreelec.amlogic.dolbyvision.level5.override = 280,280,0,0
```

### Franchise glob

`/Movies/override.ini`:
```ini
[Mission - Impossible*.mkv]
coreelec.amlogic.dolbyvision.cmv40.append = 2
```

### TV season folder — global plus one-off

`/TV/Show Name/Season 01/override.ini`:
```ini
[global]
coreelec.amlogic.dolbyvision.cmv40.append = 2

# Episode 03's RPU has L2 trims that fight the CMv4.0 path — fall back to no-L2 for it only.
[Show Name - S01E03*.mkv]
coreelec.amlogic.dolbyvision.cmv40.append = 1
```

### Force L5 enable surfaces on for a folder

`/Movies/IMAX Enhanced/override.ini`:
```ini
# Drive overlay-active-area calc from L5 metadata, even if it's globally off.
coreelec.amlogic.dolbyvision.level5 = true
coreelec.amlogic.dolbyvision.std.source.metadata.level5 = true
coreelec.amlogic.dolbyvision.detect.active.area = true
```

### Clear an override per-file

`/Movies/override.ini`:
```ini
[global]
coreelec.amlogic.dolbyvision.level5.override = 140,140,0,0

# This title's RPU has correct L5 — drop the override and let the stream drive overlay calc.
[Pristine Master.mkv]
coreelec.amlogic.dolbyvision.level5.override =
```

## Lifecycle

- Saved values are captured at `onAVStarted` per setting written.
- Restored on `onPlayBackStopped` / `onPlayBackEnded` / `onPlayBackError`.
- If the service is aborted mid-playback, the addon attempts one final
  restore on shutdown — best-effort, not guaranteed (Kodi may force-kill).

## Deferrals

- Skips `coreelec.amlogic.dolbyvision.audio.seamlessbranch` if
  `service.p3i.sb` is installed — the SB helper owns that key via its
  curated list and `SB` / `SB.txt` marker logic. Two writers on the same
  setting around the same playback event would race.

Note: this addon does **not** defer to PlexMod4Kodi. PM4K's Plex playback
streams over http(s) URLs which are already filtered (`REMOTE_SCHEMES`),
and for local-file playback through PM4K the user clearly wants their
override.ini to apply. Unlike the SB helper, there's no shared-setting
contention with PM4K to worry about.

## Verified settings

A "verified" setting is one whose Kodi C++ consumer reacts to mid-playback
writes (typically: `OnSettingChanged` callback + atomic-cached value, or
live re-push to sysfs). Settings outside this table can still be written
via `override.ini`, but the addon logs a warning and the write may be a
no-op until the next codec re-init.

Status legend:
- **live** — atomic-cached, picked up per-packet or per-frame. Late writes
  from `onAVStarted` are fine.
- **live-via-sysfs** — change handler re-pushes the underlying sysfs flag.
  Live after the corresponding C++ patch lands.
- **live-on-next-cue** — value is cached in a render-time style struct, but
  an observer fires on settings change and the next drawn subtitle picks
  it up. Applies within one cue (typically <1s for dense dialogue, longer
  for sparse subs).
- **lav-class** — sampled once at codec/stream open and cached. Needs a
  C++ patch before late writes take effect.
- **needs-restart** — sampled at codec/stream/demuxer open or app startup
  and never re-read. Mid-playback write may apply to the next playback
  but not the current one. The addon writes anyway and logs a warning.

### Dolby Vision

| Setting ID | Status | Notes |
| --- | --- | --- |
| `coreelec.amlogic.dolbyvision.cmv40.append` | live | Atomic-cached in `CDVDVideoCodecAmlogic`, applied per-packet from `AddData()`. Values: `0`=off, `1`=CMv2.9-without-L2-trims, `2`=always. **Writable only when DV type = Display-LED (0), no VP override, and DV mode != 2** — those are visible-dependencies on the setting. On other DV paths (Player-LED / LLDV / VS10) Kodi rejects the JSON-RPC write with `InvalidParams` and the codec zeroes the value anyway (CMv4.0 only matters when the TV does the tonemapping). |
| `coreelec.amlogic.dolbyvision.level5.override` | live | L5 active-area override string `"top,bottom,left,right"` (RPU active-area space) or empty. Substituted into `doviFrame/StreamMetadata` during RPU parse. When set, also short-circuits the L5 auto-detect path (override wins anyway). Affects Kodi-side overlay-active-area calc only — the emitted RPU still carries the stream's original L5. |
| `coreelec.amlogic.dolbyvision.level5` | live-via-sysfs | Master L5 enable. `aml_dv_apply_l5_sysfs()` re-pushed on change. |
| `coreelec.amlogic.dolbyvision.std.source.metadata.level5` | live-via-sysfs | Forward source L5 metadata. |
| `coreelec.amlogic.dolbyvision.std.source.metadata.level5.osdst` | live-via-sysfs | L5 OSD-start signaling. |
| `coreelec.amlogic.dolbyvision.level5.signal.subs` | live-via-sysfs | L5 subtitle signaling mode (integer). |
| `coreelec.amlogic.dolbyvision.detect.active.area` | live-via-sysfs | L5 active-area auto-detect. |

### Audio

| Setting ID | Status | Notes |
| --- | --- | --- |
| `coreelec.amlogic.dolbyvision.audio.seamlessbranch` | live | LAV SB mode. **Skipped if `service.p3i.sb` is installed** — use that addon instead. Values: `0`=off, `1`=seek-sync, `3`=debug, `4`=LAV SB, `5`=LAV full. |

### Subtitles — PGS HDR-to-SDR shader params

These are read on every PGS bitmap render and fed straight to the GPU
shader, so per-folder tuning is fully live.

| Setting ID | Status | Notes |
| --- | --- | --- |
| `subtitles.pgshdrtosdr.brightness` | live | `m_pqRefNits` shader uniform. |
| `subtitles.pgshdrtosdr.saturation` | live | `m_pqSaturation` shader uniform. |
| `subtitles.pgshdrtosdr.tonemap`    | live | Shader tone-mapping pipeline selector. |
| `subtitles.pgshdrtosdr.mode`       | live | Tonemapping algorithm: Classic / Linear / Luma. |
| `subtitles.pgshdrtosdr`            | needs-restart | **Master enable**. Sampled at PGS codec open; flipping it mid-playback won't take effect. Set globally and use the per-folder params above for tuning. |

### Subtitles — other live render-time

| Setting ID | Status | Notes |
| --- | --- | --- |
| `subtitles.captionsalign`     | live | Per-frame horizontal alignment in `ConvertLibass`. |
| `subtitles.stereoscopicdepth` | live | Per-frame 3D offset. |
| `subtitles.bitmapzoom`        | live | Per-frame bitmap scale + GPU texture filter. |

### Subtitles — style (live on next cue)

These are cached in `m_overlayStyle` and refreshed by a settings observer.
Changes apply when the next subtitle line is drawn — under a second for
dense dialogue, longer if subtitles are sparse. No C++ patch needed.

| Setting ID | Status | Notes |
| --- | --- | --- |
| `subtitles.fontname`         | live-on-next-cue | |
| `subtitles.fontsize`         | live-on-next-cue | Scaled by `playResY`. |
| `subtitles.style`            | live-on-next-cue | Bold / italic. |
| `subtitles.colorpick`        | live-on-next-cue | Font color. |
| `subtitles.bordersize`       | live-on-next-cue | ASS Outline. |
| `subtitles.bordercolorpick`  | live-on-next-cue | ASS OutlineColour. |
| `subtitles.opacity`          | live-on-next-cue | Font opacity. |
| `subtitles.blur`             | live-on-next-cue | |
| `subtitles.backgroundtype`   | live-on-next-cue | Outline / box / etc. |
| `subtitles.shadowcolor`      | live-on-next-cue | ASS BackColour. |
| `subtitles.shadowopacity`    | live-on-next-cue | |
| `subtitles.shadowsize`       | live-on-next-cue | ASS Shadow. |
| `subtitles.bgcolorpick`      | live-on-next-cue | Background color. |
| `subtitles.bgopacity`        | live-on-next-cue | |
| `subtitles.marginvertical`   | live-on-next-cue | **NOTE**: source-level comment warns that mid-playback changes cause seek artifacts — prefer setting at the start of playback. |
| `subtitles.align`            | live-on-next-cue | ASS alignment. |
| `subtitles.overridefonts`    | live-on-next-cue | Override ASS-embedded fonts. |
| `subtitles.overridestyles`   | live-on-next-cue | Override ASS style enum. |
| `subtitles.overrideass`      | live-on-next-cue | Apply override flags. |

### Subtitles — needs-restart

Sampled at stream open. Mid-playback writes don't take effect on the
current playback; set these globally instead, or accept that the change
lands on the *next* playback.

| Setting ID | Status | Notes |
| --- | --- | --- |
| `subtitles.charset`        | needs-restart | Applied at libass Configure(). |
| `subtitles.parsecaptions`  | needs-restart | Sampled during demux setup. |
| `locale.subtitlelanguage`  | needs-restart | Read at subtitle-track selection. |

---

Setting an unverified key isn't blocked, but the warning in the Kodi log
tells you the timing isn't guaranteed. If you've validated a new key,
add an entry to `resources/lib/verified_settings.py` and this table.
