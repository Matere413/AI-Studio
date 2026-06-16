import modal
import os
import subprocess

app = modal.App("download-persona-models")
image = modal.Image.debian_slim().apt_install("curl")
vol = modal.Volume.from_name("comfy-models-disk")

@app.function(image=image, volumes={"/models": vol}, timeout=1800)
def download_models():
    print("Downloading RealVisXL V4.0...")
    os.makedirs("/models/checkpoints", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/checkpoints/RealVisXL_V4.0.safetensors",
        "https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors"
    ])
    
    print("Downloading IP-Adapter FaceID Plus V2...")
    os.makedirs("/models/ipadapter", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/ipadapter/ip-adapter-faceid-plusv2_sdxl.bin",
        "https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl.bin"
    ])

    print("Downloading CLIP Vision...")
    os.makedirs("/models/clip_vision", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors"
    ])

    print("Downloading AntelopeV2 for InsightFace...")
    os.makedirs("/models/insightface/models/antelopev2", exist_ok=True)
    
    # Remove the corrupted 404 HTML file if it exists
    bad_file = "/models/insightface/models/antelopev2/106pdet_330m.onnx"
    if os.path.exists(bad_file):
        os.remove(bad_file)
        
    files = ["1k3d68.onnx", "glintr100.onnx", "scrfd_10g_bnkps.onnx", "genderage.onnx", "2d106det.onnx"]
    for f in files:
        subprocess.run([
            "curl", "-L", "-f", "-o", f"/models/insightface/models/antelopev2/{f}",
            f"https://huggingface.co/DIAMONIK7777/antelopev2/resolve/main/{f}"
        ])
    
    vol.commit()
    print("Download complete. Models are now cached in the Modal volume.")

@app.local_entrypoint()
def main():
    download_models.remote()