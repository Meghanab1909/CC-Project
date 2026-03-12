import os


def build_image(tag: str, context: str, no_cache: bool) -> dict:
    if not os.path.isdir(context):
        raise FileNotFoundError(f"Build context '{context}' does not exist")

    docksmithfile_path = os.path.join(context, "Docksmithfile")
    if not os.path.isfile(docksmithfile_path):
        raise FileNotFoundError(f"No Docksmithfile found in '{context}'")

    return {
        "success": True,
        "message": (
            f"Build started for {tag}\n"
            f"Context: {context}\n"
            f"No cache: {no_cache}"
        )
    }
