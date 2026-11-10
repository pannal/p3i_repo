# Changelog

Fork of [sualfred/script.embuary.helper](https://github.com/sualfred/script.embuary.helper) (original author: Sualfred, GPL-2.0-only), maintained by cybergrimes. Base: upstream `matrix` branch at version 2.0.9. Language files are untouched.

## 2.0.9 (cybergrimes fork, local review build)

- **PVR channel matching fix** (`resources/lib/helper.py`, `get_channeldetails`): compared an encoded `bytes` value to a `str`, which can never match in Python 3, so channel details were never found. Now compares `str` to `str`.
- **Library tag sync fix** (`resources/lib/helper.py`, `sync_library_tags`): removed items from a list while iterating it, which skipped entries. Now iterates over a copy.
- **Pillow 10+ compatibility** (`resources/lib/image.py`): `Image.ANTIALIAS` was removed in Pillow 10. Uses `Image.Resampling.LANCZOS` when available, falling back to `Image.LANCZOS` (identical filter) on older Pillow.
- **Python 3 fix** (`resources/lib/image.py`): `os.errno` no longer exists; uses `errno.EEXIST`.
- **Cleanup** (`resources/lib/image.py`, `resources/lib/utils.py`): removed no-op `from __future__ import division`.
- **Performance** (`resources/lib/helper.py`, `winprop`): `xbmcgui.Window` objects are cached per window id instead of being recreated on every call.
- **Metadata** (`addon.xml`): version 2.0.9, fork attribution and source URL, `<news>`; license (GPL-2.0-only) unchanged.
- Added this `CHANGELOG.md`.

### Deferred ideas (need owner approval)

- Debounce / only-on-finish library tag sync.
- Reduce the 3 s `waitForAbort` or the retries.
- Per-session cache of PVR channel lookups.
