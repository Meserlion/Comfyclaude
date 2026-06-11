#!/usr/bin/env python3
"""
ComfyUI image generation script for Claude.
Supports UNET+CLIP+VAE (FLUX/AuraFlow/Lumina2) workflows.

Usage: python comfyui_generate.py "your prompt here" [options]

Options:
  --negative "text"     Negative prompt (ignored for CFG=1 models)
  --steps N             Sampling steps (default: 9)
  --width N             Image width (default: 1024)
  --height N            Image height (default: 1024)
  --cfg N               CFG scale (default: 1.0)
  --seed N              Seed (-1 for random, default: -1)
  --unet "name"         UNET model filename (default: auto-detect)
  --clip "name"         CLIP model filename (default: auto-detect)
  --vae "name"          VAE model filename (default: ae.safetensors)
  --clip-type "type"    CLIP type: lumina2, flux, sd3 etc (default: lumina2)
  --no-lora             Skip LoRA loading
  --lora "name"         LoRA filename (default: auto-detect)
  --output "path"       Output file path (default: auto-generated)
  --host "url"          ComfyUI host (default: http://127.0.0.1:8000)
  --list-models         List available models and exit
"""

import argparse
import json
import random
import sys
import time
import urllib.request
import urllib.error
import os
import uuid
from pathlib import Path

COMFY_HOST = "http://127.0.0.1:8000"
OUTPUT_DIR = Path(r"C:\Users\Chris\Documents\Claude\Projects\comfyui")

def api_get(path, host=COMFY_HOST):
    url = f"{host}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def api_post(path, data, host=COMFY_HOST):
    url = f"{host}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_node_options(node_name, param_name, host=COMFY_HOST):
    try:
        info = api_get(f"/object_info/{node_name}", host)
        inputs = info[node_name]["input"]["required"]
        if param_name in inputs and isinstance(inputs[param_name][0], list):
            return inputs[param_name][0]
    except Exception:
        pass
    return []

def list_all_models(host=COMFY_HOST):
    print("=== Available Models ===")
    for node, param in [
        ("UNETLoader", "unet_name"),
        ("CheckpointLoaderSimple", "ckpt_name"),
        ("CLIPLoader", "clip_name"),
        ("VAELoader", "vae_name"),
        ("LoraLoader", "lora_name"),
    ]:
        opts = get_node_options(node, param, host)
        if opts:
            print(f"\n{node}.{param}:")
            for o in opts:
                print(f"  {o}")

def build_unet_workflow(prompt, steps, width, height, cfg, seed,
                         unet, clip, vae, clip_type, lora=None):
    if seed == -1:
        seed = random.randint(0, 2**32 - 1)

    nodes = {}

    # Load UNET
    nodes["1"] = {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": unet, "weight_dtype": "default"}
    }

    # Load CLIP
    nodes["2"] = {
        "class_type": "CLIPLoader",
        "inputs": {"clip_name": clip, "type": clip_type, "device": "default"}
    }

    # Load VAE
    nodes["3"] = {
        "class_type": "VAELoader",
        "inputs": {"vae_name": vae}
    }

    model_ref = ["1", 0]

    # Optional LoRA
    if lora:
        nodes["4"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": lora,
                "strength_model": 1.0
            }
        }
        model_ref = ["4", 0]

    # ModelSamplingAuraFlow (needed for res_multistep / Lumina2 / AuraFlow style)
    nodes["5"] = {
        "class_type": "ModelSamplingAuraFlow",
        "inputs": {"model": model_ref, "shift": 3.0}
    }

    # Positive text encode
    nodes["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": ["2", 0]}
    }

    # Negative = zero conditioning
    nodes["7"] = {
        "class_type": "ConditioningZeroOut",
        "inputs": {"conditioning": ["6", 0]}
    }

    # Empty latent
    nodes["8"] = {
        "class_type": "EmptySD3LatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1}
    }

    # KSampler
    nodes["9"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["5", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["8", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "res_multistep",
            "scheduler": "simple",
            "denoise": 1.0
        }
    }

    # VAE Decode
    nodes["10"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["9", 0], "vae": ["3", 0]}
    }

    # Save Image
    nodes["11"] = {
        "class_type": "SaveImage",
        "inputs": {"images": ["10", 0], "filename_prefix": "claude_gen"}
    }

    return {"prompt": nodes, "client_id": str(uuid.uuid4())}

def wait_for_result(prompt_id, host=COMFY_HOST, timeout=300):
    start = time.time()
    print(f"Generating... (prompt_id: {prompt_id})", flush=True)
    last_print = start
    while time.time() - start < timeout:
        try:
            history = api_get(f"/history/{prompt_id}", host)
            if prompt_id in history:
                job = history[prompt_id]
                status = job.get("status", {})
                if status.get("completed", False) or status.get("status_str") == "success":
                    elapsed = time.time() - start
                    print(f"  Done in {elapsed:.1f}s", flush=True)
                    return job
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    raise RuntimeError(f"ComfyUI error: {msgs}")
        except urllib.error.URLError:
            pass
        if time.time() - last_print > 10:
            elapsed = int(time.time() - start)
            print(f"  Still generating... ({elapsed}s)", flush=True)
            last_print = time.time()
        time.sleep(1)
    raise TimeoutError(f"Generation timed out after {timeout}s")

def fetch_image(filename, subfolder, file_type, output_path, host=COMFY_HOST):
    url = f"{host}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
    urllib.request.urlretrieve(url, output_path)

def main():
    parser = argparse.ArgumentParser(description="Generate images via ComfyUI API")
    parser.add_argument("prompt", nargs="?", default="a beautiful landscape", help="The image prompt")
    parser.add_argument("--steps", type=int, default=9)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--cfg", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--unet", default=None)
    parser.add_argument("--clip", default=None)
    parser.add_argument("--vae", default="ae.safetensors")
    parser.add_argument("--clip-type", default="lumina2")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--no-lora", action="store_true")
    parser.add_argument("--output", default=None)
    parser.add_argument("--host", default=COMFY_HOST)
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()

    # Check ComfyUI is running
    try:
        api_get("/system_stats", args.host)
    except Exception:
        print(f"ERROR: Cannot connect to ComfyUI at {args.host}")
        print("Please make sure ComfyUI is running.")
        sys.exit(1)

    if args.list_models:
        list_all_models(args.host)
        sys.exit(0)

    # Video-model names to skip when auto-detecting for image generation
    def prefer_image_model(options):
        video_markers = ("wan", "i2v", "t2v", "flf2v", "fun-inp", "umt5", "hunyuan_video", "ltx")
        image_first = [o for o in options if not any(m in o.lower() for m in video_markers)]
        return image_first or options

    # Auto-detect UNET
    unet = args.unet
    if not unet:
        unets = prefer_image_model(get_node_options("UNETLoader", "unet_name", args.host))
        if not unets:
            print("ERROR: No UNET models found. Please install a model.")
            sys.exit(1)
        unet = unets[0]
        print(f"Using UNET: {unet}")

    # Auto-detect CLIP
    clip = args.clip
    if not clip:
        clips = prefer_image_model(get_node_options("CLIPLoader", "clip_name", args.host))
        if not clips:
            print("ERROR: No CLIP models found.")
            sys.exit(1)
        clip = clips[0]
        print(f"Using CLIP: {clip}")

    # Auto-detect LoRA (optional)
    lora = None
    if not args.no_lora:
        if args.lora:
            lora = args.lora
        else:
            loras = get_node_options("LoraLoader", "lora_name", args.host)
            if loras:
                lora = loras[0]
                print(f"Using LoRA: {lora}")

    print(f"Using VAE: {args.vae}")

    # Build output path
    if args.output:
        output_path = args.output
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        output_path = str(OUTPUT_DIR / f"generated_{ts}.png")

    # Build and submit workflow
    workflow = build_unet_workflow(
        prompt=args.prompt,
        steps=args.steps,
        width=args.width,
        height=args.height,
        cfg=args.cfg,
        seed=args.seed,
        unet=unet,
        clip=clip,
        vae=args.vae,
        clip_type=args.clip_type,
        lora=lora,
    )

    print(f"Submitting workflow to ComfyUI...")
    result = api_post("/prompt", workflow, args.host)
    prompt_id = result["prompt_id"]

    # Wait for completion
    job = wait_for_result(prompt_id, args.host)

    # Extract image
    outputs = job.get("outputs", {})
    image_info = None
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            image_info = node_output["images"][0]
            break

    if not image_info:
        print("ERROR: No image in outputs.")
        print(json.dumps(outputs, indent=2))
        sys.exit(1)

    filename = image_info["filename"]
    subfolder = image_info.get("subfolder", "")
    file_type = image_info.get("type", "output")

    print(f"Fetching image: {filename}")
    fetch_image(filename, subfolder, file_type, output_path, args.host)

    print(f"SUCCESS: Image saved to {output_path}")
    return output_path

if __name__ == "__main__":
    main()
