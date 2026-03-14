import argparse
import sys

from builder.build_engine import build_image
from utils.image_store import list_images, remove_image
from runtime.runtime import run_container


def validate_image_ref(image_ref: str):
    parts = image_ref.split(":")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid image reference '{image_ref}'. Expected format: name:tag"
        )
    return parts[0], parts[1]


def parse_env_list(env_list):
    env_dict = {}
    for item in env_list:
        if "=" not in item:
            raise ValueError(
                f"Invalid env override '{item}'. Expected format: KEY=VALUE"
            )
        key, value = item.split("=", 1)
        if not key:
            raise ValueError(
                f"Invalid env override '{item}'. Key cannot be empty"
            )
        env_dict[key] = value
    return env_dict


def handle_build(args):
    validate_image_ref(args.tag)
    result = build_image(
        tag=args.tag,
        context=args.context,
        no_cache=args.no_cache
    )
    print(result["message"])


def handle_images(args):
    images = list_images()
    if not images:
        print("No images found.")
        return

    print(f"{'NAME':<15} {'TAG':<10} {'ID':<12} {'CREATED'}")
    for img in images:
        short_id = img["digest"].replace("sha256:", "")[:12]
        print(
            f"{img['name']:<15} "
            f"{img['tag']:<10} "
            f"{short_id:<12} "
            f"{img['created']}"
        )


def handle_rmi(args):
    validate_image_ref(args.image)
    result = remove_image(args.image)
    print(result["message"])


def handle_run(args):
    validate_image_ref(args.image)
    env_overrides = parse_env_list(args.env)
    cmd_override = args.cmd if args.cmd else None

    result = run_container(
        image_ref=args.image,
        env_overrides=env_overrides,
        cmd_override=cmd_override
    )
    print(result["message"])


def main():
    parser = argparse.ArgumentParser(prog="docksmith")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("-t", "--tag", required=True, help="Image name:tag")
    build_parser.add_argument("context", help="Build context directory")
    build_parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    build_parser.set_defaults(func=handle_build)

    images_parser = subparsers.add_parser("images")
    images_parser.set_defaults(func=handle_images)

    rmi_parser = subparsers.add_parser("rmi")
    rmi_parser.add_argument("image", help="Image name:tag")
    rmi_parser.set_defaults(func=handle_rmi)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument(
        "-e", "--env", action="append", default=[],
        help="Env override KEY=VALUE"
    )
    run_parser.add_argument("image", help="Image name:tag")
    run_parser.add_argument(
        "cmd", nargs=argparse.REMAINDER,
        help="Optional command override"
    )
    run_parser.set_defaults(func=handle_run)

    args = parser.parse_args()

    try:
        args.func(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
