# sd-webui-shutdown-neo

An SD WebUI NeoForge extension that allows users to shut down the WebUI process or the host system.

Inspired by [EnsignMK/sd_shutdown_button](https://github.com/EnsignMK/sd_shutdown_button).

## Features

- Shut down the WebUI with a single button.
- Shut down the host system with a single button. This is a dangerous operation.

## Installation

Clone or copy this repository into the SD WebUI NeoForge `extensions` directory, then restart
your SD WebUI NeoForge. A **Shutdown** tab will appear in the WebUI.

## Usage

- **Shutdown WebUI** terminates the WebUI process after a three-second delay, so the
  WebUI can return the success response first. It uses the same process-stop mechanism
  as the Extensions tab's **Apply changes and restart** action when a restart is unavailable.
- **Shutdown system** requires an explicit confirmation checkbox and uses the native
  shutdown command for Windows, Linux, or macOS after a three-second delay. The delay
  lets the WebUI return the success response before the host begins shutting down.

The system command runs with the privileges of the account that launched WebUI.
On Linux and macOS, that account must already be permitted to shut down the host.

## Localization

The extension uses SD WebUI NeoForge's built-in localization system. English is the
default. Simplified Chinese translations are included for the `zh-Hans (Stable)`, `zh-Hans
(Testing)`, their `[vladmandic]` variants, and `zh_Hans` localization profiles. Select one of these profiles in
**Settings > User interface > Localization**, then apply settings and reload the UI.
The status messages returned after pressing a shutdown button use the same selected
profile and its NeoForge localization dictionary.

## Why this?

I sometimes use SD WebUI from my phone while in bed, leaving my computer running at my desk.
Rather than get out of bed to turn it off, I made this extension so that I can shut down the
WebUI, or even the computer itself, and then go to sleep.

## Security notice

Shutting down the system running the WebUI can be dangerous when the WebUI is publicly accessible.
Therefore, system-level shutdown is available only to users accessing the WebUI from the local
machine or a local area network (LAN).

The extension authorizes system shutdown only when the actual connection peer is a
loopback, private, or link-local IP address. It rejects any request that carries a
forwarding header (`Forwarded`, `X-Forwarded-*`, or `X-Real-IP`), so do not expect
system shutdown to work through a reverse proxy. This is intentional: a proxy on the
same machine could otherwise make public requests look local.

The author is not responsible for any damage caused by this extension. Use it at your own risk.

## Copyright

Copyright (C) 2026 SNWCreations. Licensed under the GNU Affero General Public License v3.0.

See LICENSE file for more information.
