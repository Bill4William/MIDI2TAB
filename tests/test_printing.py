"""
Tests for cross-platform printing (src/pdf_exporter.open_for_print).
OS calls are mocked, so nothing is actually printed.
"""

import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import pdf_exporter
from src.pdf_exporter import open_for_print


class TestOpenForPrint(unittest.TestCase):
    def test_mac_sends_to_lp(self):
        with mock.patch.object(pdf_exporter.sys, "platform", "darwin"), \
             mock.patch.object(pdf_exporter.subprocess, "run") as run, \
             mock.patch.object(pdf_exporter.subprocess, "Popen") as popen:
            self.assertEqual(open_for_print("/tmp/x.pdf"), "Sent to printer.")
        self.assertEqual(run.call_args[0][0], ["lp", "/tmp/x.pdf"])
        popen.assert_not_called()

    def test_mac_without_printer_opens_preview(self):
        err = subprocess.CalledProcessError(1, ["lp"])
        with mock.patch.object(pdf_exporter.sys, "platform", "darwin"), \
             mock.patch.object(pdf_exporter.subprocess, "run", side_effect=err), \
             mock.patch.object(pdf_exporter.subprocess, "Popen") as popen:
            msg = open_for_print("/tmp/x.pdf")
        self.assertIn("PDF viewer", msg)
        popen.assert_called_once_with(["open", "/tmp/x.pdf"])

    def test_linux_without_lp_uses_xdg_open(self):
        with mock.patch.object(pdf_exporter.sys, "platform", "linux"), \
             mock.patch.object(pdf_exporter.subprocess, "run",
                               side_effect=FileNotFoundError), \
             mock.patch.object(pdf_exporter.subprocess, "Popen") as popen:
            open_for_print("/tmp/x.pdf")
        popen.assert_called_once_with(["xdg-open", "/tmp/x.pdf"])

    def test_windows_uses_print_verb(self):
        startfile = mock.Mock()
        with mock.patch.object(pdf_exporter.sys, "platform", "win32"), \
             mock.patch.object(pdf_exporter.os, "startfile", startfile, create=True):
            self.assertEqual(open_for_print("C:\\x.pdf"), "Sent to printer.")
        startfile.assert_called_once_with("C:\\x.pdf", "print")


if __name__ == "__main__":
    unittest.main()
