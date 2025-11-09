#!/usr/bin/env python3
import os
import sys
from datetime import datetime
import tomli_w
import tomllib

def init_project(project_name):
    if os.path.exists(project_name):
        print(f"Error: Directory '{project_name}' already exists.")
        return

    # Create folder structure
    os.makedirs(os.path.join(project_name, "src"), exist_ok=True)
    os.makedirs(os.path.join(project_name, "lib"), exist_ok=True)

    # Create a sample main.drop file
    main_file = os.path.join(project_name, "src", "main.drop")
    with open(main_file, "w") as f:
        f.write("// Your Droplet code starts here\n")

    # Create drip.toml
    drip_file = os.path.join(project_name, "drip.toml")
    data = {
        "project": {
            "name": project_name,
            "created": datetime.now().strftime("%Y-%m-%d")
        },
        "modules": {}
    }
    with open(drip_file, "wb") as f:
        tomli_w.dump(data, f)

    print(f"Project '{project_name}' initialized successfully!")
    print(f"Folder structure created:\n- src/main.drop\n- lib/\n- drip.toml")

def main():
    if len(sys.argv) < 3:
        print("Usage: drip init <project_name>")
        return

    command = sys.argv[1]
    if command == "init":
        project_name = sys.argv[2]
        init_project(project_name)
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
