"""Unit tests for disk_scanner (stdlib only)."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Project root on sys.path for `import disk_scanner`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import disk_scanner as ds  # noqa: E402


class TestListingThreshold(unittest.TestCase):
    def test_production_min_is_50mb(self):
        self.assertEqual(ds.MIN_FILE_SIZE_BYTES, 50 * 1024 * 1024)


class TestFormatters(unittest.TestCase):
    def test_format_size_bytes(self):
        self.assertEqual(ds.format_size(0), "0 B")
        self.assertEqual(ds.format_size(1023), "1023 B")

    def test_format_size_kb_plus(self):
        self.assertTrue(ds.format_size(1024).endswith(" KB"))
        self.assertIn("MB", ds.format_size(2 * 1024 * 1024))

    def test_format_timestamp(self):
        s = ds.format_timestamp(0.0)
        self.assertRegex(s, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


class TestExcludedPaths(unittest.TestCase):
    def test_literal_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a"
            p.mkdir()
            self.assertFalse(ds.is_excluded_path(str(p)))

    def test_under_excluded_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.realpath(tmp)
            with mock.patch.object(ds, "EXCLUDED_PATH_PREFIXES", (prefix,)):
                self.assertTrue(ds.is_excluded_path(os.path.join(tmp, "nested")))


class TestScanDirectory(unittest.TestCase):
    """scan_directory uses a patched small MIN in tests to avoid huge temp files."""

    _TEST_MIN = 1024 * 1024  # 1 MiB while production MIN is 50 MiB

    def setUp(self):
        patcher = mock.patch.object(ds, "MIN_FILE_SIZE_BYTES", self._TEST_MIN)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def test_finds_large_file_sorts_desc(self):
        small = Path(self.root) / "small.bin"
        large = Path(self.root) / "large.bin"
        huge = Path(self.root) / "huge.bin"
        small.write_bytes(b"x" * (self._TEST_MIN // 2))
        large.write_bytes(b"y" * (self._TEST_MIN + 1))
        huge.write_bytes(b"z" * (self._TEST_MIN + 100))

        rows = ds.scan_directory(self.root)
        paths = [r[0] for r in rows]
        self.assertIn(os.path.realpath(huge), paths)
        self.assertIn(os.path.realpath(large), paths)
        self.assertNotIn(os.path.realpath(small), paths)
        sizes = [r[1] for r in sorted(rows, key=lambda x: x[1], reverse=True)]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_skips_symlink_to_file(self):
        target = Path(self.root) / "real.bin"
        target.write_bytes(b"t" * (self._TEST_MIN + 1))
        link = Path(self.root) / "link.bin"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlink not supported")

        rows = ds.scan_directory(self.root)
        paths = [r[0] for r in rows]
        self.assertEqual(paths, [os.path.realpath(target)])
        # Symlink path must not be listed; realpath(link) would equal target — use abspath.
        self.assertNotIn(os.path.abspath(str(link)), paths)

    def test_skips_non_regular(self):
        fifo = Path(self.root) / "pipe"
        try:
            os.mkfifo(fifo)
        except OSError:
            self.skipTest("fifo not supported")
        rows = ds.scan_directory(self.root)
        self.assertEqual(rows, [])

    def test_atime_fallback_to_mtime(self):
        path = Path(self.root) / "f.bin"
        path.write_bytes(b"a" * (self._TEST_MIN + 1))
        st = path.stat()
        os.utime(path, (0, st.st_mtime))

        rows = ds.scan_directory(self.root)
        self.assertEqual(len(rows), 1)
        _, _, ats = rows[0]
        self.assertAlmostEqual(ats, st.st_mtime, delta=2.0)


class TestValidateRoot(unittest.TestCase):
    def test_not_exists(self):
        with self.assertRaises(SystemExit) as cm:
            ds.validate_root("/no/such/path/__disk_scanner__")
        self.assertEqual(cm.exception.code, 1)

    def test_file_not_dir(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            p = f.name
        self.addCleanup(lambda: os.unlink(p) if os.path.exists(p) else None)
        with self.assertRaises(SystemExit) as cm:
            ds.validate_root(p)
        self.assertEqual(cm.exception.code, 1)

    def test_valid_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = ds.validate_root(tmp)
            self.assertTrue(os.path.isdir(r))
            self.assertEqual(r, os.path.realpath(tmp))


class TestParseArgs(unittest.TestCase):
    def test_wrong_arity(self):
        with self.assertRaises(SystemExit) as cm:
            ds.parse_root_arg(["disk_scanner.py"])
        self.assertEqual(cm.exception.code, 2)

    def test_correct_arity(self):
        result = ds.parse_root_arg(["disk_scanner.py", "/some/path"])
        self.assertEqual(result, "/some/path")


class TestFormatSizeLargeUnits(unittest.TestCase):
    def test_gb(self):
        self.assertIn("GB", ds.format_size(2 * 1024 ** 3))

    def test_tb(self):
        self.assertIn("TB", ds.format_size(2 * 1024 ** 4))


class TestAnsiForSize(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(ds._ansi_for_size(ds.MIN_FILE_SIZE_BYTES), "")

    def test_warning(self):
        self.assertEqual(ds._ansi_for_size(ds.WARNING_SIZE_BYTES + 1), ds.YELLOW)

    def test_critical(self):
        self.assertEqual(ds._ansi_for_size(ds.CRITICAL_SIZE_BYTES + 1), ds.RED)


class TestRenderTable(unittest.TestCase):
    def _capture(self, rows):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            ds.render_table(rows)
            return fake_out.getvalue()

    def test_empty(self):
        out = self._capture([])
        self.assertIn("No files above", out)

    def test_header_and_row(self):
        rows = [("/tmp/big.bin", 100 * 1024 * 1024, 0.0)]
        out = self._capture(rows)
        self.assertIn("SIZE", out)
        self.assertIn("LAST ACCESS", out)
        self.assertIn("PATH", out)
        self.assertIn("/tmp/big.bin", out)
        self.assertIn("MB", out)

    def test_separator_line(self):
        rows = [("/tmp/a.bin", 60 * 1024 * 1024, 0.0)]
        out = self._capture(rows)
        lines = out.splitlines()
        self.assertTrue(any(set(l.strip()) == {"-"} for l in lines))

    def test_warning_color_applied(self):
        size = ds.WARNING_SIZE_BYTES + 1
        rows = [("/tmp/warn.bin", size, 0.0)]
        out = self._capture(rows)
        self.assertIn(ds.YELLOW, out)
        self.assertIn(ds.RESET, out)

    def test_critical_color_applied(self):
        size = ds.CRITICAL_SIZE_BYTES + 1
        rows = [("/tmp/crit.bin", size, 0.0)]
        out = self._capture(rows)
        self.assertIn(ds.RED, out)
        self.assertIn(ds.RESET, out)

    def test_normal_size_no_color(self):
        size = ds.MIN_FILE_SIZE_BYTES + 1
        rows = [("/tmp/normal.bin", size, 0.0)]
        out = self._capture(rows)
        self.assertNotIn(ds.YELLOW, out)
        self.assertNotIn(ds.RED, out)


class TestMainE2E(unittest.TestCase):
    """End-to-end tests that invoke disk_scanner.py as a subprocess."""

    SCANNER = str(ROOT / "disk_scanner.py")

    def _run(self, *args, **kwargs):
        return subprocess.run(
            [sys.executable, self.SCANNER, *args],
            capture_output=True,
            text=True,
            **kwargs,
        )

    def test_no_args_exits_2(self):
        r = self._run()
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", r.stderr)

    def test_nonexistent_path_exits_1(self):
        r = self._run("/no/such/path/__disk_scanner_e2e__")
        self.assertEqual(r.returncode, 1)
        self.assertIn("error", r.stderr)

    def test_file_instead_of_dir_exits_1(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            p = f.name
        try:
            r = self._run(p)
            self.assertEqual(r.returncode, 1)
        finally:
            os.unlink(p)

    def test_empty_dir_prints_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run(tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn("No files above", r.stdout)

    def test_large_file_appears_in_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            large = Path(tmp) / "big.bin"
            large.write_bytes(b"x" * (ds.MIN_FILE_SIZE_BYTES + 1))
            r = self._run(tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn("big.bin", r.stdout)
            self.assertIn("MB", r.stdout)

    def test_small_file_absent_from_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "small.bin"
            small.write_bytes(b"x" * 1024)
            r = self._run(tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn("No files above", r.stdout)


if __name__ == "__main__":
    unittest.main()
