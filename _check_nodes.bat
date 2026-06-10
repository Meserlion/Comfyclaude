@echo off
cd /d "%~dp0"
python -c "
import urllib.request, json, sys

host = 'http://127.0.0.1:8000'

try:
    with urllib.request.urlopen(f'{host}/system_stats', timeout=5) as r:
        print('ComfyUI: RUNNING')
except Exception as e:
    print(f'ComfyUI: NOT RUNNING - {e}')
    sys.exit(1)

# Get all available node types
with urllib.request.urlopen(f'{host}/object_info', timeout=10) as r:
    all_nodes = list(json.loads(r.read()).keys())

# Check for style transfer relevant nodes
keywords = ['IPAdapter', 'ipadapter', 'StyleAligned', 'Reference', 'ControlNet', 'Img2Img', 'img2img', 'LoadImage', 'UploadImage', 'CLIP', 'Redux', 'Style']
print('\\n=== Relevant nodes ===')
for n in sorted(all_nodes):
    if any(k.lower() in n.lower() for k in keywords):
        print(f'  {n}')

# List LoRAs
try:
    info = json.loads(urllib.request.urlopen(f'{host}/object_info/LoraLoader', timeout=5).read())
    loras = info['LoraLoader']['input']['required']['lora_name'][0]
    print(f'\\n=== LoRAs ({len(loras)}) ===')
    for l in loras: print(f'  {l}')
except: pass

# List UNETs
try:
    info = json.loads(urllib.request.urlopen(f'{host}/object_info/UNETLoader', timeout=5).read())
    unets = info['UNETLoader']['input']['required']['unet_name'][0]
    print(f'\\n=== UNETs ({len(unets)}) ===')
    for u in unets: print(f'  {u}')
except: pass
" > _check_nodes_output.txt 2>&1
