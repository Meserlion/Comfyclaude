import urllib.request, json, sys

host = 'http://127.0.0.1:8000'

try:
    urllib.request.urlopen(f'{host}/system_stats', timeout=5)
    print('ComfyUI: RUNNING')
except Exception as e:
    print(f'ComfyUI: NOT RUNNING - {e}')
    sys.exit(1)

# List video-related nodes
with urllib.request.urlopen(f'{host}/object_info', timeout=20) as r:
    all_nodes = list(json.loads(r.read()).keys())
kw = ['wan', 'ltx', 'video', 'animate', 'svd', 'mochi', 'hunyuan', 'cosmos', 'frame']
print()
print('=== Video-related nodes ===')
for n in sorted(all_nodes):
    if any(k in n.lower() for k in kw):
        print(f'  {n}')

# List models
for node, param in [('UNETLoader', 'unet_name'),
                    ('CheckpointLoaderSimple', 'ckpt_name'),
                    ('CLIPLoader', 'clip_name'),
                    ('VAELoader', 'vae_name'),
                    ('CLIPVisionLoader', 'clip_name')]:
    try:
        info = json.loads(urllib.request.urlopen(f'{host}/object_info/{node}', timeout=5).read())
        opts = info[node]['input']['required'][param][0]
        print()
        print(f'=== {node} ===')
        for o in opts:
            print(f'  {o}')
    except Exception:
        pass
