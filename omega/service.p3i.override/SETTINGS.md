# override.ini reference

`service.p3i.override` watches for playback and applies per-folder Kodi
setting overrides from an `override.ini` file next to the playing file.

## File location

One `override.ini` per folder, in the **same folder as the playing file**.
No parent walking — for TV that's typically the season folder; for movies
it's either the per-movie folder or a shared movies folder (use sections in
the latter case).

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

- Defers entirely while `Window(10000).Property(script.plex.running)` is set
  (PlexMod4Kodi runs its own playback).
- Skips `coreelec.amlogic.dolbyvision.audio.seamlessbranch` if
  `service.p3i.sb` is installed — the SB helper owns that key via its
  curated list and `SB` / `SB.txt` marker logic. Two writers on the same
  setting around the same playback event would race.

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
- **lav-class** — sampled once at codec/stream open and cached. Needs a
  C++ patch before late writes take effect.

| Setting ID | Status | Notes |
| --- | --- | --- |
| `coreelec.amlogic.dolbyvision.cmv40.append` | live | Atomic-cached in `CDVDVideoCodecAmlogic`, applied per-packet from `AddData()`. Values: `0`=off, `1`=CMv2.9-without-L2-trims, `2`=always. |
| `coreelec.amlogic.dolbyvision.level5.override` | live | L5 active-area override string `"top,bottom,left,right"` (RPU active-area space) or empty. Substituted into `doviFrame/StreamMetadata` during RPU parse. Affects Kodi-side overlay-active-area calc only — the emitted RPU still carries the stream's original L5. |
| `coreelec.amlogic.dolbyvision.level5` | live-via-sysfs | Master L5 enable. `aml_dv_apply_l5_sysfs()` re-pushed on change. |
| `coreelec.amlogic.dolbyvision.std.source.metadata.level5` | live-via-sysfs | Forward source L5 metadata. |
| `coreelec.amlogic.dolbyvision.std.source.metadata.level5.osdst` | live-via-sysfs | L5 OSD-start signaling. |
| `coreelec.amlogic.dolbyvision.level5.signal.subs` | live-via-sysfs | L5 subtitle signaling mode (integer). |
| `coreelec.amlogic.dolbyvision.detect.active.area` | live-via-sysfs | L5 active-area auto-detect. |
| `coreelec.amlogic.dolbyvision.audio.seamlessbranch` | live | LAV SB mode. **Skipped if `service.p3i.sb` is installed** — use that addon instead. Values: `0`=off, `1`=seek-sync, `3`=debug, `4`=LAV SB, `5`=LAV full. |

Setting an unverified key isn't blocked, but the warning in the Kodi log
tells you the timing isn't guaranteed. If you've validated a new key,
add an entry to `resources/lib/verified_settings.py` and this table.
