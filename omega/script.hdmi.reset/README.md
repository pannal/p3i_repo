# p3i HDMI Reset

An optional Program add-on for manual recovery of an Amlogic HDMI connection.
It briefly switches the HDMI transmitter off, waits one second, then switches it
on again. The receiver and TV can then reacquire the signal without restarting
Kodi or selecting a different input. Video and audio are interrupted briefly.

The supplied reset sequence was reported to recover an HDMI sync problem in an
Ugoos/Denon setup. Recovery on every receiver/TV chain is not guaranteed. This is
a manual workaround, not a correction to the underlying sync problem.

## Install and use

Install **p3i HDMI Reset** from **p3i → Program add-ons**, then run it from
Program add-ons when HDMI recovery is needed. It requires Linux/CoreELEC,
Kodi's Python3 API and writable Amlogic HDMI PHY control.

To recover when the screen is blank, configure a remote button beforehand through
Keymap Editor: **Edit → Global → Add-ons → Launch p3i HDMI Reset**. The action is
`RunAddon(script.hdmi.reset)`. A window-specific mapping can override Global.

## SSH

```sh
python3 /storage/.kodi/addons/script.hdmi.reset/default.py
```

Append `--check` to verify that the PHY control exists and is writable without
changing HDMI. Kodi invocations use `special://temp/hdmi-reset.lock`; the installed
SSH invocation uses the matching `<Kodi home>/temp/hdmi-reset.lock`. Overlapping
invocations of this addon are rejected. It attempts to re-enable HDMI in `finally`
if disabling or the delay raises; process termination can interrupt that attempt.

The addon is invoked manually. It has no background service or network requests,
and it does not modify Kodi settings, EDID, Dolby Vision policy or CEC state.
