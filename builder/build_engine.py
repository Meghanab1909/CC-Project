import os
from builder.parser import parse_docksmithfile

def build_image(tag: str, context: str, no_cache: bool) -> dict:
    if not os.path.isdir(context):
        raise FileNotFoundError(f"Build context '{context}' does not exist")

    docksmithfile_path = os.path.join(context, "Docksmithfile")
    if not os.path.isfile(docksmithfile_path):
        raise FileNotFoundError(f"No Docksmithfile found in '{context}'")
    
    instructions = parse_docksmithfile(docksmithfile_path)

    print("\nParsing Docksmithfile...\n")
    
    total_steps = len(instructions)
    
    for i, step in enumerate(instructions, start=1):
    	print(f"Step {i}/{total_steps} : {step['type']} {step['args']}")
        
    return {
        "success": True,
        "message": (
            f"Build started for {tag}\n"
            f"Context: {context}\n"
            f"No cache: {no_cache}"
        )
    }
