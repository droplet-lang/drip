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

def run_shell(cmd, cwd=None, hide_output=False):
    try:
        if hide_output:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}\n{e}")
        sys.exit(1)

# ---------- Commands ----------
def init_project(project_name, mist=False):
    if os.path.exists(project_name):
        print(f"Error: Directory '{project_name}' already exists.")
        return

    os.makedirs(os.path.join(project_name, ".dp_modules"), exist_ok=True)
    os.makedirs(os.path.join(project_name, "build"), exist_ok=True)  # create build folder

    # main.drop in root
    main_file = os.path.join(project_name, "main.drop")
    with open(main_file, "w") as f:
        f.write("// Your Droplet code starts here\n")

    # Create drip.toml with default config
    drip_file = os.path.join(project_name, "drip.toml")
    data = {
        "project": {
            "name": project_name,
            "type": "mist" if mist else "normal",
            "created": datetime.now().strftime("%Y-%m-%d")
        },
        "modules": {},
        "build": {
            "output_dir": "build",
            "main_file": "main.drop",
        },
        "mist": {
            "assets_dir": "android/app/src/main/assets",
            "gradle_task": "assembleDebug",
            "package_name": "com.mist.example",
            "main_activity": "MainActivity"
        },
        "scripts": {
            "compile": "droplet compile main.drop -o build/hello.dbc",
            "start": ""
        }
    }
    save_drip_toml(data, drip_file)

    # Mist setup
    if mist:
        android_dir = os.path.join(project_name, "android")
        print(f"Downloading Mist Android project ...")
        git_cmd = f"git clone --recursive https://github.com/droplet-lang/mist.git \"{android_dir}\""
        run_shell(git_cmd, hide_output=True)
        print("Mist project downloaded successfully!")

    print(f"Project '{project_name}' initialized successfully!")
    print(f"Folder structure created:\n- main.drop\n- build/\n- .dp_modules/\n- drip.toml")
    if mist:
        print("- android/ (Mist project)")

# ---------- Updated run_script ----------
def run_script(script_name):
    ensure_project_exists()
    project_path = os.getcwd()
    data, _ = load_drip_toml(project_path)
    scripts = data.get("scripts", {})

    if script_name not in scripts:
        print(f"Script '{script_name}' not found in drip.toml")
        return

    cmd = scripts[script_name]
    build_dir = data.get("build", {}).get("output_dir", "build")
    main_file = data.get("build", {}).get("main_file", "main.drop")

    if not cmd:
        if script_name in ("compile", "start"):
            print(f"Compiling {main_file}...")
            os.makedirs(build_dir, exist_ok=True)
            run_shell(f"droplet compile {main_file} -o {build_dir}/hello.dbc")
            print("Compilation complete.")

            if data["project"].get("type") == "mist":
                assets_dir = data.get("mist", {}).get("assets_dir", "android/app/src/main/assets")
                os.makedirs(assets_dir, exist_ok=True)
                shutil.copytree(build_dir, assets_dir, dirs_exist_ok=True)
                print("Assets copied to Android project.")

            if script_name == "start":
                android_dir = os.path.join(project_path, "android")
                gradlew = "gradlew.bat" if os.name == "nt" else "./gradlew"
                gradle_task = data.get("mist", {}).get("gradle_task", "assembleDebug")
                print(f"Building Mist Android APK ({gradle_task}) ...")
                run_shell(f"{gradlew} {gradle_task}", cwd=android_dir)

                apk_path = os.path.join(android_dir, "app", "build", "outputs", "apk", "debug", "app-debug.apk")
                if not os.path.exists(apk_path):
                    print("Error: APK not found!")
                    return

                result = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
                devices = [line.split()[0] for line in result.stdout.splitlines() if "\tdevice" in line]
                if not devices:
                    print("No connected devices found.")
                    return
                device = devices[0]
                print(f"Using device: {device}")

                package_name = data.get("mist", {}).get("package_name", "com.mist.app")
                main_activity = data.get("mist", {}).get("main_activity", "MainActivity")

                print(f"Installing APK...")
                run_shell(f"adb -s {device} install -r {apk_path}")

                print(f"Launching Mist app...")
                run_shell(f"adb -s {device} shell am start -n {package_name}/.{main_activity}")
                print("Mist app started successfully!")
        else:
            print(f"Script '{script_name}' has no command configured.")
    else:
        run_shell(cmd)

# ---------- Module Management ----------
def install_module(repo_url, version=None, visited=None, stack=None):
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

    if os.path.exists(target_dir):
        print(f"Module '{module_name}' already installed.")
    else:
        print(f"Downloading module '{module_name}' ...")
        git_cmd = f"git clone --depth 1 {'--branch ' + version if version else ''} \"{repo_url}\" \"{target_dir}\""
        run_shell(git_cmd, hide_output=True)
        print(f"Module '{module_name}' downloaded successfully!")

    # Update drip.toml
    if module_name not in data["modules"]:
        data["modules"][module_name] = {
            "source": repo_url,
            "version": version or "main",
            "installed": datetime.now().strftime("%Y-%m-%d"),
            "dependencies": []
        }
    save_drip_toml(data, drip_file)

    # Recursively install dependencies
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
                    if dep_name not in data["modules"][module_name]["dependencies"]:
                        data["modules"][module_name]["dependencies"].append(dep_name)
        save_drip_toml(data, drip_file)

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
    if module_name in data["modules"]:
        del data["modules"][module_name]
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

    if command == "init":
        if len(sys.argv) < 3:
            print("Usage: drip init <project_name> [--mist]")
            return
        mist_flag = "--mist" in sys.argv
        init_project(sys.argv[2], mist=mist_flag)
    elif command == "install" and len(sys.argv) == 3:
        install_module(sys.argv[2])
    elif command == "remove" and len(sys.argv) == 3:
        remove_module(sys.argv[2])
    elif command == "list":
        list_modules()
    elif command == "run" and len(sys.argv) == 3:
        run_script(sys.argv[2])
    else:
        print(f"Unknown command or wrong usage: {command}")
        print("Supported commands: init, install, remove, list, run")

if __name__ == "__main__":
    main()
