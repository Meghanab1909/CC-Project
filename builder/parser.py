import json

VALID_INSTRUCTIONS = {"FROM", "COPY", "RUN", "WORKDIR", "ENV", "CMD"}

def parse_docksmithfile(path: str):
    instructions = []

    with open(path, "r") as f:
        lines = f.readlines()

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # ignore comments or blank lines
        if not line or line.startswith("#"):
            continue

        parts = line.split(maxsplit=1)
        instruction = parts[0].upper()

        if instruction not in VALID_INSTRUCTIONS:
            raise ValueError(
                f"Unknown instruction '{instruction}' at line {line_number}"
            )

        if len(parts) < 2:
            raise ValueError(
                f"Missing arguments for '{instruction}' at line {line_number}"
            )

        args = parts[1]

        # ENV validation
        if instruction == "ENV":
            if "=" not in args:
                raise ValueError(
                    f"Invalid ENV format at line {line_number}. Expected KEY=value"
                )

        # CMD validation
        if instruction == "CMD":
            try:
                cmd = json.loads(args)
                if not isinstance(cmd, list):
                    raise ValueError()
            except:
                raise ValueError(
                    f"CMD must be JSON array format at line {line_number}"
                )

        instructions.append({
            "type": instruction,
            "args": args,
            "line": line_number
        })

    return instructions
