"""Tests for VFS implementations (LocalVFS, ArchiveVFS, VirtualFolderVFS, RemoteVFS)."""

import os
import shutil
import tempfile
import unittest
import zipfile
import tarfile

from pycommander.vfs import LocalVFS, FileStat
from pycommander.archive_vfs import ArchiveVFS
from pycommander.virtual_folder_vfs import VirtualFolderVFS, RemoteVFS


class TestVFS(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vfs = LocalVFS()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_local_vfs_basic_ops(self):
        sub = os.path.join(self.test_dir, "sub")
        self.vfs.make_dir(sub)
        self.assertTrue(self.vfs.exists(sub))
        self.assertTrue(self.vfs.is_dir(sub))

        fpath = os.path.join(sub, "test.txt")
        self.vfs.write_bytes(fpath, b"Hello World")
        self.assertTrue(self.vfs.exists(fpath))
        self.assertEqual(self.vfs.read_bytes(fpath), b"Hello World")

        st = self.vfs.stat(fpath)
        self.assertEqual(st.size, 11)
        self.assertEqual(st.name, "test.txt")
        self.assertEqual(st.extension, "txt")

        # Attribute preservation
        self.vfs.set_attributes(fpath, mode=0o755, mtime=1600000000.0)
        st2 = self.vfs.stat(fpath)
        self.assertEqual(int(st2.mtime), 1600000000)

        # List dir
        listing = self.vfs.list_dir(sub)
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0].name, "test.txt")

        # Rename
        fpath2 = os.path.join(sub, "renamed.txt")
        self.vfs.rename(fpath, fpath2)
        self.assertFalse(self.vfs.exists(fpath))
        self.assertTrue(self.vfs.exists(fpath2))

        # Delete
        self.vfs.remove_file(fpath2)
        self.assertFalse(self.vfs.exists(fpath2))

    def test_archive_vfs_zip(self):
        zip_path = os.path.join(self.test_dir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("folder/doc.txt", "zip content")
            zf.writestr("top.txt", "top level")

        arc = ArchiveVFS(zip_path)
        self.assertTrue(arc.is_dir("/"))
        root_items = arc.list_dir("/")
        names = [i.name for i in root_items]
        self.assertIn("folder", names)
        self.assertIn("top.txt", names)

        sub_items = arc.list_dir("/folder")
        self.assertEqual(len(sub_items), 1)
        self.assertEqual(sub_items[0].name, "doc.txt")
        self.assertEqual(arc.read_bytes("/folder/doc.txt"), b"zip content")

        # Direct write inside archive
        arc.write_bytes("/folder/new.txt", b"new inside zip")
        self.assertEqual(arc.read_bytes("/folder/new.txt"), b"new inside zip")
        self.assertTrue(arc.exists("/folder/new.txt"))

        # Remove from archive
        arc.remove_file("/folder/new.txt")
        self.assertFalse(arc.exists("/folder/new.txt"))

    def test_archive_vfs_tar_gz(self):
        tar_path = os.path.join(self.test_dir, "test.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tf:
            data = b"tar content"
            import io
            ti = tarfile.TarInfo(name="mydir/file.txt")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))

        arc = ArchiveVFS(tar_path, format_type="tar.gz")
        self.assertTrue(arc.exists("/mydir/file.txt"))
        self.assertEqual(arc.read_bytes("/mydir/file.txt"), b"tar content")

    def test_virtual_folder_vfs(self):
        f1 = os.path.join(self.test_dir, "hit1.txt")
        f2 = os.path.join(self.test_dir, "hit2.log")
        self.vfs.write_bytes(f1, b"one")
        self.vfs.write_bytes(f2, b"two")

        st1 = self.vfs.stat(f1)
        st2 = self.vfs.stat(f2)

        vfolder = VirtualFolderVFS("Search Hits", [st1, st2])
        items = vfolder.list_dir("/")
        self.assertEqual(len(items), 2)
        self.assertEqual(vfolder.read_bytes(st1.path), b"one")

    def test_remote_vfs_mock(self):
        remote = RemoteVFS(protocol="sftp", host="example.com")
        remote.write_bytes("/remote_file.txt", b"remote content")
        self.assertTrue(remote.exists("/remote_file.txt"))
        self.assertEqual(remote.read_bytes("/remote_file.txt"), b"remote content")
        items = remote.list_dir("/")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "remote_file.txt")


if __name__ == "__main__":
    unittest.main()
