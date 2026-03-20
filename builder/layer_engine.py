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
    return sha.hexdigest()   # plain hex, NO "sha256:" prefix


def create_layer(files):
    """
    Create a tar of the given files.
    Returns (temp_path, digest) where digest is a plain hex string (no sha256: prefix).
    Callers store it as:  digest + ".tar"  for the filename
    and                  "sha256:" + digest  in the JSON manifest.
    """
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar")
    temp.close()

    with tarfile.open(temp.name, "w") as tar:
        for file in sorted(files):          # sorted for reproducibility
            if os.path.exists(file):
                info = tar.gettarinfo(file, arcname=os.path.basename(file))
                info.mtime = 0              # zero timestamp for reproducibility
                if os.path.islink(file):
                    tar.addfile(info)
                else:
                    with open(file, "rb") as f:
                        tar.addfile(info, f)

    digest = sha256_file(temp.name)        # plain hex
    return temp.name, digest
