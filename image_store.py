def list_images():
    return [
        {
            "name": "myapp",
            "tag": "latest",
            "digest": "sha256:abcdef1234567890abcdef1234567890",
            "created": "2026-03-12T20:00:00"
        }
    ]


def remove_image(image_ref: str) -> dict:
    return {
        "success": True,
        "message": f"Removed image {image_ref}"
    }
