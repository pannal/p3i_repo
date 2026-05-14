# p3i Kodi repo

Kodi addon repository for the [p3i CoreELEC build](https://github.com/pannal/CoreELEC) (aml-4.9-21.3 lineage).

Hosts binary and Python addons built specifically against p3i's Kodi + FFmpeg sysroot. **Not intended for use on stock CoreELEC** — binaries here dynamically link against FFmpeg 8.1 and other p3i system libraries, and will fail to load on firmware shipping older FFmpeg.

## Install

On p3i firmware the repo is **pre-installed by default** — no manual step needed. p3i appears under *Add-ons → Install from repository*.

For older p3i builds or sideloading: download `repository.p3i-*.zip` from [p3irepo.pm4k.eu](https://p3irepo.pm4k.eu/) and install via *Add-ons → Install from zip file*.
