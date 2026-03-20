import os
import json
import hashlib
import pwd


def _get_docksmith_dir() -> str:
    """
    Always return the real user's ~/.docksmith, even when running under sudo.
    This ensures build (sudo) and run (sudo) both use the same directory.
    """
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        home = pwd.getpwnam(sudo_user).pw_dir
    else:
        home = os.path.expanduser("~")
    return os.path.join(home, ".docksmith")


# These are functions so they always resolve correctly at call time
def _images_dir():  return os.path.join(_get_docksmith_dir(), "images")
def _layers_dir():  return os.path.join(_get_docksmith_dir(), "layers")
def _cache_dir():   return os.path.join(_get_docksmith_dir(), "cache")


# Module-level constants — resolved once at import time
# (used by build_engine imports like: from utils.image_store import LAYERS_DIR)
DOCKSMITH_DIR = _get_docksmith_dir()
IMAGES_DIR    = _images_dir()
LAYERS_DIR    = _layers_dir()
CACHE_DIR     = _cache_dir()


def init_storage():
    for d in [IMAGES_DIR, LAYERS_DIR, CACHE_DIR]:
        os.makedirs(d, exist_ok=True)


def save_image(manifest: dict):
    init_storage()
    filename = f"{manifest['name']}_{manifest['tag']}.json"
    path = os.path.join(IMAGES_DIR, filename)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def load_image(name: str, tag: str) -> dict:
    path = os.path.join(IMAGES_DIR, f"{name}_{tag}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {name}:{tag}")
    with open(path) as f:
        return json.load(f)


def list_images() -> list:
    init_storage()
    images = []
    for fname in sorted(os.listdir(IMAGES_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(IMAGES_DIR, fname)) as f:
                images.append(json.load(f))
    return images


def remove_image(name: str, tag: str) -> dict:
    manifest = load_image(name, tag)

    # Collect digests used by ALL other images so we don't delete shared layers
    protected = set()
    for fname in os.listdir(IMAGES_DIR):
        if fname.endswith(".json") and fname != f"{name}_{tag}.json":
            with open(os.path.join(IMAGES_DIR, fname)) as f:
                other = json.load(f)
            for layer in other.get("layers", []):
                protected.add(layer["digest"].replace("sha256:", ""))

    # Only delete layers NOT used by any other image
    for layer in manifest.get("layers", []):
        digest     = layer["digest"].replace("sha256:", "")
        if digest in protected:
            print(f"  Keeping shared layer: {digest[:12]}...")
            continue
        layer_path = os.path.join(LAYERS_DIR, digest + ".tar")
        if os.path.exists(layer_path):
            os.remove(layer_path)
            print(f"  Deleted layer: {digest[:12]}...")

    os.remove(os.path.join(IMAGES_DIR, f"{name}_{tag}.json"))
    return {"success": True, "message": f"Removed image {name}:{tag}"}
