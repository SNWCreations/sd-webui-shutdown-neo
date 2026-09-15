"""Unit tests for the shutdown extension's non-UI behavior."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "shutdown_tab.py"
LOCALIZATIONS_PATH = Path(__file__).parents[1] / "localizations"


def load_shutdown_tab():
    """Load the extension with host dependencies replaced by small test doubles."""
    gradio = types.ModuleType("gradio")
    gradio.Request = object

    callbacks = types.ModuleType("modules.script_callbacks")
    callbacks.on_ui_tabs = lambda callback: None

    restart = types.ModuleType("modules.restart")
    restart.stop_program = lambda: None

    localization = types.ModuleType("modules.localization")
    localization.calls = []
    localization.translations = {
        "zh-Hans (Stable)": {
            "System shutdown requested. It will begin in 3 seconds. You can safely close this window now.": "已请求关闭系统，将在 3 秒后开始。现在可以安全关闭此窗口。",
        },
        "zh_Hans": {
            "WebUI shutdown requested. It will begin in 3 seconds. You can safely close this window now.": "已请求关闭 WebUI，将在 3 秒后开始。现在可以安全关闭此窗口。",
        },
    }

    def localization_js(profile):
        localization.calls.append(profile)
        return "window.localization = " + json.dumps(
            localization.translations.get(profile, {})
        )

    localization.localization_js = localization_js

    state = types.SimpleNamespace(server_command=None)
    modules = types.ModuleType("modules")
    modules.localization = localization
    modules.restart = restart
    modules.script_callbacks = callbacks
    modules.shared = types.SimpleNamespace(
        state=state,
        opts=types.SimpleNamespace(localization="None"),
    )

    spec = importlib.util.spec_from_file_location("shutdown_tab_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    with patch.dict(
        sys.modules,
        {
            "gradio": gradio,
            "modules": modules,
            "modules.localization": localization,
            "modules.restart": restart,
            "modules.script_callbacks": callbacks,
        },
    ):
        spec.loader.exec_module(module)
    return module


class FakeRequest:
    def __init__(self, host: str, headers=None):
        self.client = types.SimpleNamespace(host=host)
        self.headers = headers or {}


class ShutdownTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extension = load_shutdown_tab()

    def setUp(self):
        self.extension.shared.opts = types.SimpleNamespace(localization="None")

    def test_local_and_lan_addresses_are_allowed(self):
        for host in ("127.0.0.1", "::1", "192.168.1.20", "10.0.0.8", "fe80::1%12"):
            with self.subTest(host=host):
                self.assertTrue(self.extension.is_local_or_lan_host(host))

    def test_public_and_invalid_addresses_are_rejected(self):
        for host in (None, "", "8.8.8.8", "example.com"):
            with self.subTest(host=host):
                self.assertFalse(self.extension.is_local_or_lan_host(host))

    def test_forwarded_requests_are_rejected(self):
        request = FakeRequest("127.0.0.1", {"X-Forwarded-For": "203.0.113.5"})
        self.assertFalse(self.extension.is_system_shutdown_allowed(request))

    def test_response_text_defaults_to_english(self):
        self.assertEqual(
            self.extension.response_text("Confirm system shutdown before continuing."),
            "Confirm system shutdown before continuing.",
        )
        self.assertEqual(self.extension.localization.calls[-1], "None")

    def test_response_text_uses_simplified_chinese_for_zh_hans_profile(self):
        self.extension.shared.opts = types.SimpleNamespace(
            localization="zh-Hans (Stable)"
        )

        self.assertEqual(
            self.extension.response_text(
                "System shutdown requested. It will begin in 3 seconds. You can safely close this window now."
            ),
            "已请求关闭系统，将在 3 秒后开始。现在可以安全关闭此窗口。",
        )
        self.assertEqual(self.extension.localization.calls[-1], "zh-Hans (Stable)")

    def test_response_text_supports_underscore_zh_hans_profile(self):
        self.extension.shared.opts = types.SimpleNamespace(localization="zh_Hans")

        self.assertEqual(
            self.extension.response_text(
                "WebUI shutdown requested. It will begin in 3 seconds. You can safely close this window now."
            ),
            "已请求关闭 WebUI，将在 3 秒后开始。现在可以安全关闭此窗口。",
        )
        self.assertEqual(self.extension.localization.calls[-1], "zh_Hans")

    def test_webui_shutdown_is_scheduled(self):
        with patch.object(self.extension, "schedule_webui_shutdown") as schedule:
            message = self.extension.request_webui_shutdown()

        self.assertEqual(
            message,
            "WebUI shutdown requested. It will begin in 3 seconds. You can safely close this window now.",
        )
        schedule.assert_called_once_with()

    def test_delayed_webui_shutdown_stops_the_webui_process(self):
        with patch.object(self.extension.restart, "stop_program") as stop_program:
            self.extension._run_webui_shutdown()

        stop_program.assert_called_once_with()

    def test_webui_shutdown_timer_waits_three_seconds(self):
        with patch.object(self.extension.threading, "Timer") as timer:
            self.extension.schedule_webui_shutdown()

        timer.assert_called_once_with(3.0, self.extension._run_webui_shutdown)
        timer.return_value.start.assert_called_once_with()

    def test_system_shutdown_is_scheduled_after_authorization(self):
        request = FakeRequest("192.168.1.20")
        with patch.object(self.extension.platform, "system", return_value="Windows"), patch.object(
            self.extension, "schedule_system_shutdown"
        ) as schedule:
            message = self.extension.request_system_shutdown(True, request)

        self.assertEqual(
            message,
            "System shutdown requested. It will begin in 3 seconds. You can safely close this window now.",
        )
        schedule.assert_called_once_with(("shutdown", "/s", "/t", "0"))

    def test_system_shutdown_timer_waits_three_seconds(self):
        command = ("shutdown", "/s", "/t", "0")
        with patch.object(self.extension.threading, "Timer") as timer:
            self.extension.schedule_system_shutdown(command)

        timer.assert_called_once_with(
            3.0,
            self.extension._run_system_shutdown,
            args=(command,),
        )
        timer.return_value.start.assert_called_once_with()

    def test_delayed_system_shutdown_starts_native_command(self):
        command = ("shutdown", "/s", "/t", "0")
        with patch.object(self.extension.subprocess, "Popen") as popen:
            self.extension._run_system_shutdown(command)

        popen.assert_called_once_with(command, start_new_session=True)

    def test_system_shutdown_rejects_public_request_without_starting_process(self):
        request = FakeRequest("8.8.8.8")
        with patch.object(self.extension, "schedule_system_shutdown") as schedule:
            message = self.extension.request_system_shutdown(True, request)

        self.assertEqual(
            message, "System shutdown is available only to direct local or LAN clients."
        )
        schedule.assert_not_called()


if __name__ == "__main__":
    unittest.main()
