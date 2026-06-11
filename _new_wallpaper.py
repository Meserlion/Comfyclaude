"""Generate themed wallpapers (fire / ice / storm sisters) and set one per monitor.

Random seed every run -> new variations each time. Themes rotate across monitors
on every run (offset persisted in wallpapers/cycle_state.json). Each image is
generated at the target monitor's resolution, rounded to multiples of 16.

If ComfyUI isn't running, starts it headless in the background and shuts it down
again afterwards, so this works at system startup with nothing open.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

# The ELEMENT (woman, robes, orb, background) cycles across monitors each run.
# The POSTURE is fixed per monitor and never moves.
ELEMENTS = [
    {"name": "sun",
     "woman": "A Caucasian woman in flowing white embroidered robes",
     "orb": "a blazing miniature sun, fiery plasma tendrils swirling around the glowing orb",
     "bg": "a glowing golden galaxy"},
    {"name": "ice",
     "woman": "An African American woman in flowing black embroidered robes",
     "orb": "a glowing sphere of crystalline ice, frost mist and shimmering snowflakes "
            "swirling around the frozen orb",
     "bg": "a cold blue nebula"},
    {"name": "storm",
     "woman": "An Asian woman in flowing silver-violet embroidered robes",
     "orb": "a crackling orb of violet lightning, electric arcs and storm clouds "
            "swirling around the sphere",
     "bg": "a deep purple nebula"},
]
# keyed by monitor index from _set_wallpaper.ps1 -List (0=middle/primary, 1=right 1920x1200, 2=left)
POSTURES = {
    0: "facing the viewer directly, sitting in serene meditation in deep space, "
       "holding {orb} in front of her chest above her open palms",
    1: "in profile facing to the left, sitting in serene meditation in deep space, "
       "holding {orb} floating above her open palm extended to the left",
    2: "in profile facing to the right, sitting in serene meditation in deep space, "
       "holding {orb} floating above her open palm extended to the right",
}


def build_prompt(element, monitor_index):
    posture = POSTURES[monitor_index].format(orb=element["orb"])
    return (f"{element['woman']}, {posture}, stars and {element['bg']} in the "
            "background, cinematic lighting, ultra detailed")

HOST = "http://127.0.0.1:8000"
COMFY_PY = r"C:\Users\Chris\Documents\ComfyUI\.venv\Scripts\python.exe"
COMFY_MAIN = r"C:\Users\Chris\AppData\Local\Programs\ComfyUI\resources\ComfyUI\main.py"
COMFY_BASE = r"C:\Users\Chris\Documents\ComfyUI"
COMFY_MODEL_PATHS = r"C:\Users\Chris\AppData\Roaming\Comfy Desktop\shared_model_paths.yaml"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "wallpapers")
STATE_FILE = os.path.join(OUT_DIR, "cycle_state.json")


def comfy_up():
    try:
        with urllib.request.urlopen(f"{HOST}/system_stats", timeout=3) as r:
            json.loads(r.read())
        return True
    except Exception:
        return False


def start_comfy_headless():
    """Launch ComfyUI like the desktop app does, minus the UI. Returns the process."""
    cmd = [
        COMFY_PY, "-s", COMFY_MAIN,
        "--base-directory", COMFY_BASE,
        "--user-directory", os.path.join(COMFY_BASE, "user"),
        "--database-url", f"sqlite:///{os.path.join(COMFY_BASE, 'user', 'comfyui.db')}",
        "--port", "8000",
        "--extra-model-paths-config", COMFY_MODEL_PATHS,
        "--input-directory", os.path.join(COMFY_BASE, "input"),
        "--output-directory", os.path.join(COMFY_BASE, "output"),
        "--disable-auto-launch",
    ]
    proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 180
    while time.time() < deadline:
        if comfy_up():
            return proc
        if proc.poll() is not None:
            print("ERROR: ComfyUI process exited during startup")
            sys.exit(1)
        time.sleep(2)
    proc.terminate()
    print("ERROR: ComfyUI did not come up within 180s")
    sys.exit(1)


def list_monitors():
    result = subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", os.path.join(HERE, "_set_wallpaper.ps1"), "-List",
    ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode != 0:
        print(f"ERROR: monitor listing failed: {result.stderr}")
        sys.exit(1)
    mons = json.loads(result.stdout)
    return [mons] if isinstance(mons, dict) else mons


def set_wallpaper(path, monitor_index):
    result = subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", os.path.join(HERE, "_set_wallpaper.ps1"),
        "-Path", path, "-Monitor", str(monitor_index),
    ], creationflags=subprocess.CREATE_NO_WINDOW)
    return result.returncode == 0


def main():
    os.chdir(HERE)
    os.makedirs(OUT_DIR, exist_ok=True)

    monitors = {m["index"]: m for m in list_monitors()}
    monitor_indices = sorted(monitors)
    print(f"Found {len(monitors)} monitor(s)")

    # rotate element->monitor assignment each run; postures stay with the monitor
    offset = 0
    try:
        with open(STATE_FILE) as f:
            offset = json.load(f).get("offset", 0)
    except Exception:
        pass
    with open(STATE_FILE, "w") as f:
        json.dump({"offset": (offset + 1) % len(monitor_indices)}, f)

    started_proc = None
    if not comfy_up():
        print("ComfyUI not running - starting it headless...")
        started_proc = start_comfy_headless()

    failures = 0
    try:
        ts = int(time.time())
        for i, element in enumerate(ELEMENTS):
            mon_idx = monitor_indices[(i + offset) % len(monitor_indices)]
            mon = monitors[mon_idx]
            w = max(512, round(mon["width"] / 16) * 16)
            h = max(512, round(mon["height"] / 16) * 16)
            out_path = os.path.join(OUT_DIR, f"{element['name']}_m{mon_idx}_{ts}.png")

            print(f"[{element['name']}] generating {w}x{h} for monitor {mon_idx} "
                  f"({mon['width']}x{mon['height']}{', primary' if mon['primary'] else ''})...")
            result = subprocess.run([
                sys.executable, os.path.join(HERE, "comfyui_generate.py"),
                build_prompt(element, mon_idx),
                "--no-lora", "--width", str(w), "--height", str(h),
                "--output", out_path,
            ])
            if result.returncode != 0 or not os.path.isfile(out_path):
                print(f"[{element['name']}] ERROR: generation failed")
                failures += 1
                continue
            if set_wallpaper(out_path, mon_idx):
                print(f"[{element['name']}] set on monitor {mon_idx}")
            else:
                print(f"[{element['name']}] ERROR: failed to set wallpaper")
                failures += 1
    finally:
        if started_proc is not None:
            print("Shutting down headless ComfyUI...")
            started_proc.terminate()

    if failures:
        sys.exit(1)
    print("SUCCESS: all monitors updated")


if __name__ == "__main__":
    main()
