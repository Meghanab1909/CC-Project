"""
runtime/runtime.py
------------------
The ONE isolation primitive for Docksmith.
Used by BOTH:
  - docksmith run   →  run_container()
  - builder RUN     →  run_in_isolation() called directly from build_engine.py
"""

import os
import sys
import shutil
import tarfile
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_store import load_image, LAYERS_DIR


# ─── THE isolation primitive ──────────────────────────────────────────────────

def run_in_isolation(rootfs: str, command: list, env: dict, workdir: str = "/") -> int:
    """
    THE one isolation primitive — chroot + unshare.
    Used for both RUN (build) and docksmith run.
    """
    proc_dir = os.path.join(rootfs, "proc")
    os.makedirs(proc_dir, exist_ok=True)

    # Ensure workdir exists inside rootfs
    if workdir and workdir != "/":
        abs_workdir = os.path.join(rootfs, workdir.lstrip("/"))
        os.makedirs(abs_workdir, exist_ok=True)

    # Build the inner shell command: cd into workdir then run
    inner = subprocess.list2cmdline(command)
    if workdir and workdir != "/":
        shell_cmd = f"cd {workdir} && {inner}"
    else:
        shell_cmd = inner

    full_cmd = [
        "unshare",
        "--mount",
        "--pid",
        "--fork",
        f"--mount-proc={proc_dir}",
        "chroot", rootfs,
        "/bin/sh", "-c", shell_cmd
    ]

    try:
        result = subprocess.run(full_cmd, env=env)
        return result.returncode
    except FileNotFoundError as e:
        raise RuntimeError(
            f"'unshare' or 'chroot' not found: {e}\n"
            "Make sure you are on Linux and running with sudo."
        )
# ─── Filesystem assembly ──────────────────────────────────────────────────────

def assemble_rootfs(manifest: dict, dest_dir: str):
    for layer in manifest.get("layers", []):
        # digest in JSON is "sha256:abcdef..." — strip prefix for filename
        digest   = layer["digest"].replace("sha256:", "")
        tar_path = os.path.join(LAYERS_DIR, digest + ".tar")

        if not os.path.exists(tar_path):
            raise FileNotFoundError(
                f"Layer tar missing: {tar_path}\n"
                f"Rebuild the image to regenerate missing layers."
            )

        with tarfile.open(tar_path, "r") as tf:
            tf.extractall(path=dest_dir)

# ─── Environment builder ──────────────────────────────────────────────────────

def build_env(manifest: dict, env_overrides: dict) -> dict:
    """
    Final env dict:
      1. Minimal safe base PATH
      2. Image ENV values
      3. Runtime -e overrides  ← highest priority
    """
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/root",
        "TERM":  "xterm",
    }

    for kv in manifest.get("config", {}).get("Env", []):
        if "=" in kv:
            k, v = kv.split("=", 1)
            env[k] = v

    env.update(env_overrides)   # -e overrides win
    return env


# ─── Public API ───────────────────────────────────────────────────────────────

def run_container(image_ref: str, env_overrides: dict, cmd_override) -> dict:
    """
    Entry point called by main.py for:  docksmith run <name:tag> [cmd]

    1. Load manifest
    2. Resolve command
    3. Assemble rootfs into a temp dir
    4. run_in_isolation()
    5. Always clean up temp dir  ← guarantees no host filesystem leakage
    """
    if ":" not in image_ref:
        raise ValueError(f"Invalid image ref '{image_ref}', expected name:tag")

    name, tag = image_ref.split(":", 1)
    manifest  = load_image(name, tag)

    # Resolve command: override > image CMD
    cmd_list = list(cmd_override) if cmd_override else manifest.get("config", {}).get("Cmd", [])
    if not cmd_list:
        raise ValueError(
            f"No CMD defined in image '{image_ref}' and no command provided.\n"
            f"Usage:  docksmith run {image_ref} <command>"
        )

    workdir = manifest.get("config", {}).get("WorkingDir") or "/"
    env     = build_env(manifest, env_overrides)

    tmpdir = tempfile.mkdtemp(prefix="docksmith_run_")
    try:
        print(f"Assembling filesystem for {image_ref} ...")
        assemble_rootfs(manifest, tmpdir)

        print(f"Command : {' '.join(cmd_list)}")
        print(f"Workdir : {workdir}")
        print("-" * 40)

        exit_code = run_in_isolation(
            rootfs  = tmpdir,
            command = cmd_list,
            env     = env,
            workdir = workdir,
        )

        print("-" * 40)
        print(f"Container exited with code: {exit_code}")

        return {
            "success"   : exit_code == 0,
            "exit_code" : exit_code,
            "message"   : f"Container exited with code {exit_code}",
        }

    finally:
        # CRITICAL: always delete the temp rootfs
        # A file written inside the container lives only in tmpdir.
        # After rmtree it cannot exist on the host. This is the isolation guarantee.
        shutil.rmtree(tmpdir, ignore_errors=True)
