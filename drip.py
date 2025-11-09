#!/usr/bin/env python3
import os
import sys
import subprocess
from datetime import datetime
import tomli_w
import tomllib
import shutil

# ---------- Helpers ----------
def load_drip_toml(project_path):
    drip_file = os.path.join(project_path, "drip.toml")
    if not os.path.exists(drip_file):
        return None, drip_file
    with open(drip_file, "rb") as f:
        data = tomllib.load(f)
    return data, drip_file

def save_drip_toml(data, drip_file):
    with open(drip_file, "wb") as f:
        tomli_w.dump(data, f)

def ensure_project_exists():
    if not os.path.exists("drip.toml"):
        print("Error: Not a Drip project. Run 'drip init <project_name>' first.")
        sys.exit(1)

# ---------- Commands ----------
def init_project(project_name):
    if os.path.exists(project_name):
        print(f"Error: Directory '{project_name}' already exists.")
        return

    os.makedirs(os.path.join(project_name, "src"), exist_ok=True)
    os.makedirs(os.path.join(project_name, ".dp_modules"), exist_ok=True)

    # Create main.drop
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
    save_drip_toml(data, drip_file)

    print(f"Project '{project_name}' initialized successfully!")
    print(f"Folder structure created:\n- src/main.drop\n- .dp_modules/\n- drip.toml")

# ---------- Install with recursion and circular dependency check ----------
def install_module(repo_url, version=None, visited=None, stack=None):
    """
    Install a module and its dependencies recursively, detect circular dependencies
    """
    ensure_project_exists()

    if visited is None:
        visited = set()
    if stack is None:
        stack = []

    project_path = os.getcwd()
    module_name = os.path.basename(repo_url).replace(".git", "")

    if module_name in stack:
        print(f"Error: Circular dependency detected: {' -> '.join(stack + [module_name])}")
        return

    if module_name in visited:
        return
    visited.add(module_name)
    stack.append(module_name)

    target_dir = os.path.join(project_path, ".dp_modules", module_name)
    data, drip_file = load_drip_toml(project_path)

    # Clone if not already installed
    if os.path.exists(target_dir):
        print(f"Module '{module_name}' already installed.")
    else:
        print(f"Installing module '{module_name}' from {repo_url} ...")
        git_cmd = ["git", "clone", "--depth", "1"]
        if version:
            git_cmd += ["--branch", version]
        git_cmd += [repo_url, target_dir]

        try:
            subprocess.run(git_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to clone repository: {e}")
            stack.pop()
            return

    # Update drip.toml
    if module_name not in data["modules"]:
        data["modules"][module_name] = {
            "source": repo_url,
            "version": version or "main",
            "installed": datetime.now().strftime("%Y-%m-%d"),
            "dependencies": []
        }
    save_drip_toml(data, drip_file)

    # Check module's own drip.toml for dependencies
    module_drip_file = os.path.join(target_dir, "drip.toml")
    if os.path.exists(module_drip_file):
        with open(module_drip_file, "rb") as f:
            module_data = tomllib.load(f)
            deps = module_data.get("modules", {})
            for dep_name, dep_info in deps.items():
                dep_url = dep_info.get("source")
                dep_version = dep_info.get("version")
                if dep_url:
                    install_module(dep_url, dep_version, visited, stack.copy())
                    # Record dependency
                    if dep_name not in data["modules"][module_name]["dependencies"]:
                        data["modules"][module_name]["dependencies"].append(dep_name)
        save_drip_toml(data, drip_file)

    print(f"Module '{module_name}' installed successfully!")
    stack.pop()

def remove_module(module_name):
    ensure_project_exists()
    project_path = os.getcwd()
    data, drip_file = load_drip_toml(project_path)

    target_dir = os.path.join(project_path, ".dp_modules", module_name)
    if not os.path.exists(target_dir):
        print(f"Module '{module_name}' is not installed.")
        return

    shutil.rmtree(target_dir)

    # Remove from drip.toml
    if module_name in data["modules"]:
        del data["modules"][module_name]

    # Remove it from other module dependencies
    for mod in data["modules"].values():
        if "dependencies" in mod and module_name in mod["dependencies"]:
            mod["dependencies"].remove(module_name)

    save_drip_toml(data, drip_file)
    print(f"Module '{module_name}' removed successfully.")

def list_modules():
    ensure_project_exists()
    project_path = os.getcwd()
    data, _ = load_drip_toml(project_path)

    modules = data.get("modules", {})
    if not modules:
        print("No modules installed.")
        return

    print("Installed modules (with dependencies):")
    for name, info in modules.items():
        deps = ", ".join(info.get("dependencies", [])) or "None"
        print(f"- {name} (source: {info['source']}, version: {info.get('version','main')}, installed: {info['installed']}, deps: {deps})")

# ---------- CLI ----------
def main():
    if len(sys.argv) < 2:
        print("Usage: drip <command> [args...]")
        return

    command = sys.argv[1]

    if command == "init" and len(sys.argv) == 3:
        init_project(sys.argv[2])
    elif command == "install" and len(sys.argv) == 3:
        install_module(sys.argv[2])
    elif command == "remove" and len(sys.argv) == 3:
        remove_module(sys.argv[2])
    elif command == "list":
        list_modules()
    else:
        print(f"Unknown command or wrong usage: {command}")
        print("Supported commands: init, install, remove, list")

if __name__ == "__main__":
    main()
