import hashlib
import os


def compute_cache_key(prev_digest: str, instruction: str, workdir: str = "", env_state: dict = None, src_files_hash: str = "") -> str:
    sha = hashlib.sha256()
    sha.update(prev_digest.encode())
    sha.update(instruction.encode())
    sha.update(workdir.encode())
    env_str = ",".join(f"{k}={v}" for k, v in sorted(env_state.items())) if env_state else ""
    sha.update(env_str.encode())
    sha.update(src_files_hash.encode())   # empty string for RUN, file hashes for COPY
    return sha.hexdigest()


def check_cache(cache_dir: str, key: str) -> bool:
    return os.path.exists(os.path.join(cache_dir, key))


def store_cache(cache_dir: str, key: str, digest: str = ""):
    with open(os.path.join(cache_dir, key), "w") as f:
        f.write(digest)


def get_cached_digest(cache_dir: str, key: str) -> str:
    path = os.path.join(cache_dir, key)
    if os.path.exists(path):
        content = open(path).read().strip()
        return "" if content in ("cached", "") else content
    return ""


def hash_source_files(src_path: str) -> str:
    """SHA-256 of all source files concatenated in lexicographic path order."""
    sha = hashlib.sha256()
    if os.path.isfile(src_path):
        with open(src_path, "rb") as f:
            sha.update(f.read())
    elif os.path.isdir(src_path):
        for root, dirs, files in os.walk(src_path):
            dirs.sort()
            for fname in sorted(files):
                full = os.path.join(root, fname)
                sha.update(os.path.relpath(full, src_path).encode())
                with open(full, "rb") as f:
                    sha.update(f.read())
    return sha.hexdigest()
