import os
from tempfile import NamedTemporaryFile


def tmpfile_uris():
    tmp_files = []
    ram_disk_path = "/Volumes/RAM DISK/"
    prefix = None
    if os.path.exists(ram_disk_path):
        prefix = ram_disk_path
    while True:
        tmp_file = NamedTemporaryFile(prefix=prefix, suffix="_eventsourcing_test.db")
        tmp_files.append(tmp_file)
        yield "file:" + tmp_file.name
