"""Unit tests for the anansi CLI (skills/anansi/scripts/anansi.py).

Run:  python3 -m unittest discover -s tests
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "anansi" / "scripts"))
import anansi  # noqa: E402
import server as core  # noqa: E402

DOC = core.compose_document(
    {"id": "dQw4w9WgXcQ", "title": "Never Gonna", "channel": "Rick", "duration": 213},
    "[0:00] hello there")


class Helpers(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(anansi.safe_filename('a/b:c*d?"e<f>g|h'), "a_b_c_d__e_f_g_h")
        self.assertEqual(anansi.safe_filename("  ..  "), "untitled")
        self.assertEqual(len(anansi.safe_filename("x" * 400)), 150)

    def test_gather_text_args_and_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("https://youtu.be/abcdefghijk")
        text = anansi.gather_text(["https://www.youtube.com/watch?v=dQw4w9WgXcQ"], f.name)
        self.assertEqual(core.extract_video_ids(text), ["dQw4w9WgXcQ", "abcdefghijk"])

    def test_parse_search_json(self):
        rows = anansi.parse_search_json({"entries": [
            {"id": "dQw4w9WgXcQ", "title": "T", "channel": "C", "duration": 213.0, "view_count": 10},
            {"id": "bad", "title": "skipped"},
            {"id": "abcdefghijk", "title": "U", "uploader": "Up"}]})
        self.assertEqual([r["id"] for r in rows], ["dQw4w9WgXcQ", "abcdefghijk"])
        self.assertEqual(rows[0]["duration"], "3:33")
        self.assertEqual(rows[0]["views"], 10)
        self.assertEqual(rows[1]["channel"], "Up")
        self.assertIsNone(rows[1]["views"])
        self.assertEqual(anansi.parse_search_json({}), [])


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict("os.environ", {"XDG_CACHE_HOME": self.tmp.name})
        self.env.start()
        mock.patch.object(anansi, "ytdlp", return_value="yt-dlp").start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, *argv):
        out, errs = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(errs):
            code = anansi.main(list(argv))
        return code, out.getvalue(), errs.getvalue()

    def test_no_links(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True):
            code, _, errs = self.run_cli("fetch", "nothing here")
        self.assertEqual(code, 2)
        self.assertIn("no YouTube links", errs)

    def test_fetch_summary_caches_and_out(self):
        with mock.patch.object(core, "fetch_document", return_value=DOC) as fd:
            code, out, _ = self.run_cli("fetch", "https://youtu.be/dQw4w9WgXcQ")
            self.assertEqual(code, 0)
            self.assertIn("✓ Never Gonna — Rick [3:33]", out)
            self.assertTrue((core.cache_dir() / "dQw4w9WgXcQ.txt").is_file())
            # second run is served from the cache
            outdir = Path(self.tmp.name) / "out"
            code, out, _ = self.run_cli("fetch", "dQw4w9WgXcQ junk https://youtu.be/dQw4w9WgXcQ",
                                        "--out", str(outdir))
            self.assertEqual(fd.call_count, 1)
        written = outdir / "Never Gonna [dQw4w9WgXcQ].txt"
        self.assertEqual(written.read_text(encoding="utf-8"), DOC)
        self.assertIn(str(written), out)

    def test_fetch_stdout_and_errors(self):
        def fake(yt, vid):
            if vid == "abcdefghijk":
                raise RuntimeError("video unavailable")
            return DOC
        with mock.patch.object(core, "fetch_document", side_effect=fake):
            code, out, errs = self.run_cli("fetch", "--stdout",
                                           "youtu.be/dQw4w9WgXcQ youtu.be/abcdefghijk")
        self.assertEqual(code, 0)
        self.assertEqual(out, DOC)
        self.assertIn("✗ abcdefghijk: video unavailable", errs)

    def test_all_failed_exit_1(self):
        with mock.patch.object(core, "fetch_document", side_effect=RuntimeError("timed out")):
            code, out, _ = self.run_cli("fetch", "youtu.be/abcdefghijk")
        self.assertEqual(code, 1)
        self.assertIn("timed out", out)


if __name__ == "__main__":
    unittest.main()
