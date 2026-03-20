import os
import shutil
import tempfile
import hashlib
import json
import datetime
import tarfile
from builder.cache import compute_cache_key, check_cache, store_cache, get_cached_digest, hash_source_files
from builder.layer_engine import create_layer
from builder.cache import compute_cache_key, check_cache, store_cache, get_cached_digest
from builder.parser import parse_docksmithfile
from utils.image_store import init_storage, LAYERS_DIR, CACHE_DIR, save_image, load_image
from runtime.runtime import run_in_isolation, assemble_rootfs


def build_image(tag: str, context: str, no_cache: bool) -> dict:
    init_storage()

    if not os.path.isdir(context):
        raise FileNotFoundError(f"Build context '{context}' does not exist")

    docksmithfile_path = os.path.join(context, "Docksmithfile")
    if not os.path.isfile(docksmithfile_path):
        raise FileNotFoundError(f"No Docksmithfile found in '{context}'")

    instructions = parse_docksmithfile(docksmithfile_path)
    print("\nParsing Docksmithfile...\n")

    total_steps  = len(instructions)
    prev_digest  = "base"
    layers       = []
    config       = {"Env": [], "Cmd": [], "WorkingDir": "/"}
    env_state    = {}
    workdir      = "/"
    cache_broken = no_cache

    name, tag_only = tag.split(":", 1) if ":" in tag else (tag, "latest")

    build_rootfs = tempfile.mkdtemp(prefix="docksmith_build_")

    try:
        for i, step in enumerate(instructions, start=1):
            op   = step["type"]
            args = step["args"]
            raw  = f"{op} {args}"

            # ── FROM ──────────────────────────────────────────────────────
            if op == "FROM":
                print(f"Step {i}/{total_steps} : {raw}")
                parts     = args.split(":")
                base_name = parts[0]
                base_tag  = parts[1] if len(parts) > 1 else "latest"

                base_manifest = load_image(base_name, base_tag)
                layers        = list(base_manifest.get("layers", []))
                prev_digest   = base_manifest.get("digest", "base")
                config        = dict(base_manifest.get("config", {
                    "Env": [], "Cmd": [], "WorkingDir": "/"
                }))
                workdir = config.get("WorkingDir", "/")

                shutil.rmtree(build_rootfs, ignore_errors=True)
                os.makedirs(build_rootfs, exist_ok=True)
                assemble_rootfs(base_manifest, build_rootfs)

            # ── WORKDIR ───────────────────────────────────────────────────
            elif op == "WORKDIR":
                workdir = args.strip()
                config["WorkingDir"] = workdir
                os.makedirs(os.path.join(build_rootfs, workdir.lstrip("/")), exist_ok=True)
                print(f"Step {i}/{total_steps} : {raw}")

            # ── ENV ───────────────────────────────────────────────────────
            elif op == "ENV":
                config["Env"].append(args)
                if "=" in args:
                    k, v = args.split("=", 1)
                    env_state[k] = v
                print(f"Step {i}/{total_steps} : {raw}")

            # ── CMD ───────────────────────────────────────────────────────
            elif op == "CMD":
                try:
                    config["Cmd"] = json.loads(args)
                except Exception:
                    config["Cmd"] = args.split()
                print(f"Step {i}/{total_steps} : {raw}")

            # ── COPY ──────────────────────────────────────────────────────
            elif op == "COPY":
                src_for_hash = os.path.join(context, args.split(None, 1)[0])
                src_hash     = hash_source_files(src_for_hash)
                cache_key    = compute_cache_key(prev_digest, raw, workdir, env_state, src_hash)

                if not cache_broken and check_cache(CACHE_DIR, cache_key):
                    cached   = get_cached_digest(CACHE_DIR, cache_key)
                    tar_path = os.path.join(LAYERS_DIR, cached + ".tar")
                    if cached and os.path.exists(tar_path):
                        # Extract into build_rootfs so subsequent RUN steps see the files
                        with tarfile.open(tar_path, "r") as tf:
                            tf.extractall(path=build_rootfs)
                        print(f"Step {i}/{total_steps} : {raw} [CACHE HIT]")
                        layers.append({
                            "digest"    : f"sha256:{cached}",
                            "size"      : os.path.getsize(tar_path),
                            "createdBy" : raw,
                        })
                        prev_digest = cached
                        continue
                    else:
                        cache_broken = True

                # Execute COPY
                parts    = args.split(None, 1)
                src      = parts[0]
                dst      = parts[1].strip()
                src_path = os.path.join(context, src)
                dst_path = os.path.join(build_rootfs, dst.lstrip("/"))
                os.makedirs(dst_path, exist_ok=True)

                files_to_tar = []   # list of (host_abs_path, arcname)

                if os.path.isdir(src_path):
                    for root, dirs, filenames in os.walk(src_path):
                        dirs.sort()
                        for fname in sorted(filenames):
                            full    = os.path.join(root, fname)
                            rel     = os.path.relpath(full, src_path)
                            arcname = os.path.join(dst.lstrip("/"), rel)
                            files_to_tar.append((full, arcname))
                            out = os.path.join(build_rootfs, arcname)
                            os.makedirs(os.path.dirname(out), exist_ok=True)
                            shutil.copy2(full, out)
                elif os.path.isfile(src_path):
                    arcname = os.path.join(dst.lstrip("/"), os.path.basename(src_path))
                    files_to_tar.append((src_path, arcname))
                    out = os.path.join(build_rootfs, arcname)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    shutil.copy2(src_path, out)
                else:
                    raise FileNotFoundError(f"COPY source not found: {src_path}")

                # Build layer tar preserving full directory structure
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar")
                tmp.close()
                with tarfile.open(tmp.name, "w") as tf:
                    for host_path, arcname in sorted(files_to_tar, key=lambda x: x[1]):
                        info       = tf.gettarinfo(host_path, arcname=arcname)
                        info.mtime = 0
                        with open(host_path, "rb") as f:
                            tf.addfile(info, f)

                with open(tmp.name, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()

                layer_file = os.path.join(LAYERS_DIR, digest + ".tar")
                shutil.move(tmp.name, layer_file)
                store_cache(CACHE_DIR, cache_key, digest)

                layers.append({
                    "digest"    : f"sha256:{digest}",
                    "size"      : os.path.getsize(layer_file),
                    "createdBy" : raw,
                })
                prev_digest  = digest
                cache_broken = True
                print(f"Step {i}/{total_steps} : {raw} [CACHE MISS]")

            # ── RUN ───────────────────────────────────────────────────────
            elif op == "RUN":
                cache_key = compute_cache_key(prev_digest, raw, workdir, env_state)

                if not cache_broken and check_cache(CACHE_DIR, cache_key):
                    cached   = get_cached_digest(CACHE_DIR, cache_key)
                    tar_path = os.path.join(LAYERS_DIR, cached + ".tar")
                    if cached and os.path.exists(tar_path):
                        # Extract delta back into build_rootfs for subsequent steps
                        with tarfile.open(tar_path, "r") as tf:
                            tf.extractall(path=build_rootfs)
                        print(f"Step {i}/{total_steps} : {raw} [CACHE HIT]")
                        layers.append({
                            "digest"    : f"sha256:{cached}",
                            "size"      : os.path.getsize(tar_path),
                            "createdBy" : raw,
                        })
                        prev_digest = cached
                        continue
                    else:
                        cache_broken = True

                # Build env for RUN — inject image ENV values
                run_env = {
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "HOME": "/root",
                }
                for kv in config.get("Env", []):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        run_env[k] = v

                snap_before = _snapshot(build_rootfs)

                # ── ISOLATED RUN — same primitive as docksmith run ────────
                exit_code = run_in_isolation(
                    rootfs  = build_rootfs,
                    command = ["/bin/sh", "-c", args],
                    env     = run_env,
                    workdir = workdir,
                )

                if exit_code != 0:
                    raise RuntimeError(f"RUN failed (exit {exit_code}): {args}")

                snap_after  = _snapshot(build_rootfs)
                delta_files = _delta(build_rootfs, snap_before, snap_after)

                # Build delta layer tar
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar")
                tmp.close()
                with tarfile.open(tmp.name, "w") as tf:
                    for fpath in sorted(delta_files):
                        rel        = os.path.relpath(fpath, build_rootfs)
                        info       = tf.gettarinfo(fpath, arcname=rel)
                        info.mtime = 0
                        with open(fpath, "rb") as f:
                            tf.addfile(info, f)

                with open(tmp.name, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()

                layer_file = os.path.join(LAYERS_DIR, digest + ".tar")
                shutil.move(tmp.name, layer_file)
                store_cache(CACHE_DIR, cache_key, digest)

                layers.append({
                    "digest"    : f"sha256:{digest}",
                    "size"      : os.path.getsize(layer_file),
                    "createdBy" : raw,
                })
                prev_digest  = digest
                cache_broken = True
                print(f"Step {i}/{total_steps} : {raw} [CACHE MISS]")

            else:
                raise SyntaxError(f"Unknown instruction '{op}' — check your Docksmithfile")

        # ── Write manifest ────────────────────────────────────────────────
        # Preserve original created timestamp on cache-hit rebuilds
        # (spec: identical manifest digest across rebuilds when all steps hit)
        original_created = None
        try:
            existing         = load_image(name, tag_only)
            original_created = existing.get("created")
        except FileNotFoundError:
            pass

        manifest = {
            "name"    : name,
            "tag"     : tag_only,
            "digest"  : "",
            "created" : original_created or datetime.datetime.utcnow().isoformat(),
            "config"  : config,
            "layers"  : layers,
        }
        canonical          = json.dumps(manifest, sort_keys=True)
        digest_hex         = hashlib.sha256(canonical.encode()).hexdigest()
        manifest["digest"] = f"sha256:{digest_hex}"
        save_image(manifest)

        print(f"\nSuccessfully built sha256:{digest_hex[:12]} {name}:{tag_only}")
        return {"success": True, "message": f"Successfully built {name}:{tag_only}"}

    finally:
        shutil.rmtree(build_rootfs, ignore_errors=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _snapshot(rootfs: str) -> dict:
    """Return {relative_path: mtime} for every file in rootfs."""
    snap = {}
    for root, dirs, files in os.walk(rootfs):
        for fname in files:
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, rootfs)
            try:
                snap[rel] = os.path.getmtime(full)
            except OSError:
                pass
    return snap


def _delta(rootfs: str, before: dict, after: dict) -> list:
    """Absolute paths of files that are new or modified since before."""
    result = []
    for rel, mtime in after.items():
        if rel not in before or before[rel] != mtime:
            result.append(os.path.join(rootfs, rel))
    return result
