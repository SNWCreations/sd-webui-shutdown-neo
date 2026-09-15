"""Shutdown controls for SD WebUI NeoForge."""

from __future__ import annotations

import ipaddress
import logging
import platform
import subprocess
import threading
from typing import Optional, Sequence

import gradio as gr

from modules import restart, script_callbacks, shared


logger = logging.getLogger(__name__)
SYSTEM_SHUTDOWN_DELAY_SECONDS = 3.0


def _client_host(request: gr.Request) -> Optional[str]:
    """Return the peer address reported by Gradio/Starlette, if available."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    if host is None:
        return None
    return str(host)


def _has_forwarding_headers(request: gr.Request) -> bool:
    """Fail closed when a proxy may have obscured the actual requester."""
    headers = getattr(request, "headers", None)
    if not headers:
        return False

    forwarded_header_names = {
        "forwarded",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-real-ip",
    }
    return any(str(name).lower() in forwarded_header_names for name in headers)


def is_local_or_lan_host(host: Optional[str]) -> bool:
    """Accept loopback and private/link-local IP addresses only."""
    if not host:
        return False

    if host.lower() == "localhost":
        return True

    # IPv6 scope identifiers (for example, fe80::1%12) are not parsed by
    # ipaddress but still identify a link-local peer.
    address_text = host.split("%", 1)[0]
    try:
        address = ipaddress.ip_address(address_text)
    except ValueError:
        return False

    return address.is_loopback or address.is_private or address.is_link_local


def is_system_shutdown_allowed(request: gr.Request) -> bool:
    """Authorize only direct requests from the machine or its LAN."""
    return not _has_forwarding_headers(request) and is_local_or_lan_host(
        _client_host(request)
    )


def build_system_shutdown_command(system_name: Optional[str] = None) -> Optional[Sequence[str]]:
    """Return the native shutdown command for the current platform."""
    system_name = system_name or platform.system()
    if system_name == "Windows":
        return ("shutdown", "/s", "/t", "0")
    if system_name in {"Linux", "Darwin"}:
        return ("shutdown", "-h", "now")
    return None


def _run_system_shutdown(command: Sequence[str]) -> None:
    """Run the shutdown command after the UI response has been sent."""
    try:
        subprocess.Popen(command, start_new_session=True)
    except OSError:
        logger.exception("Could not start system shutdown command")


def schedule_system_shutdown(command: Sequence[str]) -> None:
    """Delay the shutdown so Gradio can return its success response first."""
    timer = threading.Timer(
        SYSTEM_SHUTDOWN_DELAY_SECONDS,
        _run_system_shutdown,
        args=(command,),
    )
    timer.start()


def _run_webui_shutdown() -> None:
    """Terminate the WebUI process after the UI response has been sent."""
    logger.info("WebUI shutdown started from the Shutdown tab")
    restart.stop_program()


def schedule_webui_shutdown() -> None:
    """Delay process termination so Gradio can return a success response first."""
    timer = threading.Timer(SYSTEM_SHUTDOWN_DELAY_SECONDS, _run_webui_shutdown)
    timer.start()


def request_webui_shutdown() -> str:
    """Schedule WebUI process termination after this request completes."""
    schedule_webui_shutdown()
    logger.info("WebUI shutdown requested from the Shutdown tab")
    return "WebUI shutdown requested. It will begin in 3 seconds. You can safely close this window now."


def request_system_shutdown(confirmed: bool, request: gr.Request) -> str:
    """Request an operating-system shutdown after local-network authorization."""
    if not confirmed:
        return "Confirm system shutdown before continuing."

    if not is_system_shutdown_allowed(request):
        logger.warning("Denied system shutdown request from %s", _client_host(request))
        return "System shutdown is available only to direct local or LAN clients."

    command = build_system_shutdown_command()
    if command is None:
        return "System shutdown is not supported on this platform."

    schedule_system_shutdown(command)

    logger.warning("System shutdown requested from %s", _client_host(request))
    return "System shutdown requested. It will begin in 3 seconds. You can safely close this window now."


def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as shutdown_interface:
        gr.Markdown("## Shutdown")
        status = gr.Textbox(label="Status", interactive=False, lines=2)

        webui_shutdown = gr.Button(
            "Shutdown WebUI", variant="stop", elem_id="shutdown_webui_button"
        )
        webui_shutdown.click(
            fn=request_webui_shutdown,
            inputs=None,
            outputs=status,
        )

        with gr.Accordion("System shutdown", open=False):
            confirm_system_shutdown = gr.Checkbox(
                label="I understand this will immediately shut down the host system.",
                value=False,
            )
            system_shutdown = gr.Button(
                "Shutdown system", variant="stop", elem_id="shutdown_system_button"
            )
            system_shutdown.click(
                fn=request_system_shutdown,
                inputs=confirm_system_shutdown,
                outputs=status,
            )

    return [(shutdown_interface, "Shutdown", "shutdown_tab")]


script_callbacks.on_ui_tabs(on_ui_tabs)
