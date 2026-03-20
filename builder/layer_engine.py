import tarfile
import hashlib
import tempfile
import os


def sha256_file(path):
    sha = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha.update(chunk)

    return sha.hexdigest()


def create_layer(files):
    temp = tempfile.NamedTemporaryFile(delete=False)

    with tarfile.open(temp.name, "w") as tar:
        for file in files:
            if os.path.exists(file):
                tar.add(file, arcname=os.path.basename(file))

    digest = "sha256:" + sha256_file(temp.name)

    return temp.name, digest
