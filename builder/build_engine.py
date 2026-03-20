from builder.layer_engine import create_layer
from builder.cache import compute_cache_key, check_cache, store_cache
from utils.image_store import init_storage, LAYERS_DIR, CACHE_DIR
from builder.parser import parse_docksmithfile

import shutil
import os


def build_image(tag: str, context: str, no_cache: bool) -> dict:
    # initialize storage folders
    init_storage()

    # check context folder
    if not os.path.isdir(context):
        raise FileNotFoundError(f"Build context '{context}' does not exist")

    docksmithfile_path = os.path.join(context, "Docksmithfile")

    if not os.path.isfile(docksmithfile_path):
        raise FileNotFoundError(f"No Docksmithfile found in '{context}'")

    # parse Docksmithfile
    instructions = parse_docksmithfile(docksmithfile_path)

    print("\nParsing Docksmithfile...\n")

    total_steps = len(instructions)
    prev_digest = "base"

    for i, step in enumerate(instructions, start=1):
        op = step["type"]
        args = step["args"]
        raw = f"{op} {args}"

        # ==============================
        # HANDLE COPY & RUN
        # ==============================
        if op in ["COPY", "RUN"]:
            cache_key = compute_cache_key(prev_digest, raw)

            if not no_cache and check_cache(CACHE_DIR, cache_key):
                print(f"Step {i}/{total_steps} : {raw} [CACHE HIT]")
                continue

            files = []

            # ---------- COPY ----------
            if op == "COPY":
                src, dest = args.split()

                for root, dirs, filenames in os.walk(src):
                    for f in filenames:
                        files.append(os.path.join(root, f))

            # ---------- RUN ----------
            if op == "RUN":
                temp_file = f"run_{i}.txt"

                with open(temp_file, "w") as f:
                    f.write(args)

                files.append(temp_file)

            # create layer
            layer_path, digest = create_layer(files)

            # move to layers folder
            layer_file = os.path.join(LAYERS_DIR, digest + ".tar")
            shutil.move(layer_path, layer_file)

            # store cache
            store_cache(CACHE_DIR, cache_key)

            prev_digest = digest

            print(f"Step {i}/{total_steps} : {raw} [CACHE MISS]")

        # ==============================
        # OTHER INSTRUCTIONS
        # ==============================
        else:
            print(f"Step {i}/{total_steps} : {raw}")

    return {
        "success": True,
        "message": (
            f"Successfully built {tag}\n"
            f"Context: {context}\n"
            f"No cache: {no_cache}"
        )
    }
