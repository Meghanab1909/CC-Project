import hashlib
import os


def compute_cache_key(prev_digest, instruction):
    sha = hashlib.sha256()
    sha.update(prev_digest.encode())
    sha.update(instruction.encode())
    return sha.hexdigest()


def check_cache(cache_dir, key):
    path = os.path.join(cache_dir, key)
    return os.path.exists(path)


def store_cache(cache_dir, key):
    path = os.path.join(cache_dir, key)
    with open(path, "w") as f:
        f.write("cached")

