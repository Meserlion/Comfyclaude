"""Generate a perfectly looping video from z-image_00084_.png via Wan 2.1 FLF2V.

Same image as first and last frame -> seamless loop. Duplicate end frame trimmed.
"""
import json
import os
import random
import struct
import sys
import time
import urllib.request
import uuid

HOST = "http://127.0.0.1:8000"
IMAGE = "z-image_00084_.png"
OUTPUT = "sun_loop.mp4"
FRAMES = 81          # 4n+1, ~5s @ 16fps
FPS = 16
STEPS = 30           # more steps = better temporal/lighting coherence
CFG = 5.0            # lower CFG reduces brightness pumping / flicker
SHIFT = 5.0
TRIM = 1             # Fun-InP is trained for end-frame conditioning - only the exact duplicate frame to drop

POSITIVE = (
    "A woman in flowing white embroidered robes sits in serene meditation in deep space, "
    "holding a blazing miniature sun floating above her open palm. The sun's plasma flames "
    "swirl, flicker and curl continuously, fiery tendrils dancing around the glowing orb. "
    "Stars twinkle softly, the galaxy glows gently in the background. Her robe and hair sway "
    "very subtly. She remains still and calm. Slow, gentle, cinematic ambient motion, "
    "seamless continuous movement."
)
NEGATIVE = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，"
    "低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，"
    "毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
)


def api_get(path, timeout=15):
    with urllib.request.urlopen(f"{HOST}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def api_post(path, data, timeout=30):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{HOST}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def upload_image(path):
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()
    name = os.path.basename(path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{HOST}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        api_get("/system_stats", 5)
    except Exception as e:
        print(f"ERROR: ComfyUI not reachable - {e}")
        sys.exit(1)

    # Target ~480p area, keep aspect, multiples of 16
    iw, ih = png_size(IMAGE)
    aspect = iw / ih
    area = 832 * 480
    w = int(round((area * aspect) ** 0.5 / 16) * 16)
    h = int(round((area / aspect) ** 0.5 / 16) * 16)
    print(f"Source {iw}x{ih} -> generating at {w}x{h}, {FRAMES} frames @ {FPS}fps")

    img_name = upload_image(IMAGE)
    print(f"Uploaded as: {img_name}")

    seed = random.randint(0, 2**32 - 1)
    print(f"Seed: {seed}")

    nodes = {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "Wan2.1-Fun-InP-14B_fp8_e4m3fn.safetensors",
            "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {
            "vae_name": "wan_2.1_vae.safetensors"}},
        "4": {"class_type": "CLIPVisionLoader", "inputs": {
            "clip_name": "clip_vision_h.safetensors"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": img_name}},
        "6": {"class_type": "CLIPVisionEncode", "inputs": {
            "clip_vision": ["4", 0], "image": ["5", 0], "crop": "none"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {
            "text": POSITIVE, "clip": ["2", 0]}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {
            "text": NEGATIVE, "clip": ["2", 0]}},
        "9": {"class_type": "WanFunInpaintToVideo", "inputs": {
            "positive": ["7", 0], "negative": ["8", 0], "vae": ["3", 0],
            "clip_vision_output": ["6", 0],
            "start_image": ["5", 0], "end_image": ["5", 0],
            "width": w, "height": h, "length": FRAMES, "batch_size": 1}},
        "10": {"class_type": "ModelSamplingSD3", "inputs": {
            "model": ["1", 0], "shift": SHIFT}},
        "11": {"class_type": "KSampler", "inputs": {
            "model": ["10", 0], "positive": ["9", 0], "negative": ["9", 1],
            "latent_image": ["9", 2], "seed": seed, "steps": STEPS, "cfg": CFG,
            "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "12": {"class_type": "VAEDecode", "inputs": {
            "samples": ["11", 0], "vae": ["3", 0]}},
        # trim duplicated last frame + convergence-flare frames at the seam
        "13": {"class_type": "ImageFromBatch", "inputs": {
            "image": ["12", 0], "batch_index": 0, "length": FRAMES - TRIM}},
        "14": {"class_type": "CreateVideo", "inputs": {
            "images": ["13", 0], "fps": float(FPS)}},
        "15": {"class_type": "SaveVideo", "inputs": {
            "video": ["14", 0], "filename_prefix": "sun_loop",
            "format": "mp4", "codec": "h264"}},
    }

    result = api_post("/prompt", {"prompt": nodes, "client_id": str(uuid.uuid4())})
    pid = result["prompt_id"]
    print(f"Submitted (prompt_id: {pid}). This can take a while on a 14B model...")

    start = time.time()
    last = start
    job = None
    while time.time() - start < 7200:
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
            print(f"  still generating... ({int(time.time() - start)}s)", flush=True)
            last = time.time()
        time.sleep(2)

    if job is None:
        print("ERROR: timed out after 2h")
        sys.exit(1)
    print(f"Done in {time.time() - start:.0f}s")

    # find saved video in outputs
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
