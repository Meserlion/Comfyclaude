"""Upscale sun_loop_pingpong.mp4 to ~1080p via RealESRGAN x4plus in ComfyUI.

848x464 -> 4x ESRGAN -> lanczos down to 1920x1050 (keeps source aspect).
"""
import json
import os
import sys
import time
import urllib.request
import uuid

HOST = "http://127.0.0.1:8000"
INPUT = sys.argv[1] if len(sys.argv) > 1 else "sun_loop.mp4"
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "sun_loop_1080p.mp4"
WIDTH = 1920
HEIGHT = 1050
FPS = 16.0


def api_get(path, timeout=15):
    with urllib.request.urlopen(f"{HOST}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def api_post(path, data, timeout=30):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{HOST}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def upload_file(path):
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()
    name = os.path.basename(path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{HOST}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["name"]


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        api_get("/system_stats", 5)
    except Exception as e:
        print(f"ERROR: ComfyUI not reachable - {e}")
        sys.exit(1)

    vid_name = upload_file(INPUT)
    print(f"Uploaded as: {vid_name}")

    nodes = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": vid_name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "UpscaleModelLoader", "inputs": {
            "model_name": "RealESRGAN_x4plus.pth"}},
        "4": {"class_type": "ImageUpscaleWithModel", "inputs": {
            "upscale_model": ["3", 0], "image": ["2", 0]}},
        "5": {"class_type": "ImageScale", "inputs": {
            "image": ["4", 0], "upscale_method": "lanczos",
            "width": WIDTH, "height": HEIGHT, "crop": "disabled"}},
        "6": {"class_type": "CreateVideo", "inputs": {
            "images": ["5", 0], "fps": FPS}},
        "7": {"class_type": "SaveVideo", "inputs": {
            "video": ["6", 0], "filename_prefix": "sun_loop_1080p",
            "format": "mp4", "codec": "h264"}},
    }

    result = api_post("/prompt", {"prompt": nodes, "client_id": str(uuid.uuid4())})
    pid = result["prompt_id"]
    print(f"Submitted (prompt_id: {pid})")

    start = time.time()
    last = start
    job = None
    while time.time() - start < 3600:
        try:
            hist = api_get(f"/history/{pid}")
            if pid in hist:
                j = hist[pid]
                st = j.get("status", {})
                if st.get("completed") or st.get("status_str") == "success":
                    job = j
                    break
                if st.get("status_str") == "error":
                    print("ComfyUI ERROR:")
                    print(json.dumps(st.get("messages", []), indent=2)[:3000])
                    sys.exit(1)
        except urllib.error.URLError:
            pass
        if time.time() - last > 30:
            print(f"  still upscaling... ({int(time.time() - start)}s)", flush=True)
            last = time.time()
        time.sleep(2)

    if job is None:
        print("ERROR: timed out after 1h")
        sys.exit(1)
    print(f"Done in {time.time() - start:.0f}s")

    for node_out in job.get("outputs", {}).values():
        for key in ("images", "video", "videos", "gifs"):
            for item in node_out.get(key, []):
                fn = item.get("filename", "")
                if fn.endswith((".mp4", ".webm", ".mov")):
                    sub = item.get("subfolder", "")
                    typ = item.get("type", "output")
                    url = f"{HOST}/view?filename={fn}&subfolder={sub}&type={typ}"
                    urllib.request.urlretrieve(url, OUTPUT)
                    print(f"SUCCESS: saved {OUTPUT} ({os.path.getsize(OUTPUT)} bytes)")
                    return
    print("ERROR: no video found in outputs:")
    print(json.dumps(job.get("outputs", {}), indent=2)[:2000])
    sys.exit(1)


if __name__ == "__main__":
    main()
