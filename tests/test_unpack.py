import contextlib
import io
from pathlib import Path
import sys
import tarfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pmt_capture_cli as cli
from pmt.export.archive import unpack_archive
import test_pmt_bulk_capture as fixtures


class UnpackTest(unittest.TestCase):
    setUp = fixtures.PmtBulkCaptureTest.setUp
    tearDown = fixtures.PmtBulkCaptureTest.tearDown
    _args = fixtures.PmtBulkCaptureTest._args
    _add_telem = fixtures.PmtBulkCaptureTest._add_telem

    def test_capture_pack_unpack_verifies(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.capture.run_capture(self._args("packed"))
            cli.pack_run(self.output / "packed", self.root / "packages", False)
        archive = next((self.root / "packages").glob("*.tar.gz"))
        result = unpack_archive(archive, self.root / "unpacked")
        self.assertTrue(result["verification"]["RequestedSampleCountReached"])
        self.assertEqual(Path(result["run_dir"]).name, "packed")

    def test_rejects_path_traversal_and_links(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("link", tarfile.SYMTYPE), ("hardlink", tarfile.LNKTYPE)):
            archive = self.root / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
                stream.addfile(member)
            with self.assertRaises(ValueError):
                unpack_archive(archive, self.root / "failed")
            self.assertFalse((self.root / "failed").exists())

    def test_rejects_size_count_and_duplicate_members(self):
        archive = self.root / "limits.tar"
        with tarfile.open(archive, "w") as stream:
            member = tarfile.TarInfo("payload")
            member.size = 4
            stream.addfile(member, io.BytesIO(b"data"))
        for limits in ({"max_bytes": 3}, {"max_files": 0}):
            with self.assertRaises(ValueError):
                unpack_archive(archive, self.root / "failed", **limits)
            self.assertFalse((self.root / "failed").exists())
        with tarfile.open(archive, "a") as stream:
            stream.addfile(tarfile.TarInfo("./payload"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            unpack_archive(archive, self.root / "failed")
        self.assertFalse((self.root / "failed").exists())