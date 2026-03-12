def run_container(image_ref: str, env_overrides: dict, cmd_override):
    return {
        "success": True,
        "message": (
            f"Running image: {image_ref}\n"
            f"Env overrides: {env_overrides}\n"
            f"Command override: {cmd_override}"
        )
    }
