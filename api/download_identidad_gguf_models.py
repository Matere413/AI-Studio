import modal
import os
import subprocess

app = modal.App("download-identidad-gguf-models")
image = modal.Image.debian_slim().apt_install("curl")
vol = modal.Volume.from_name("comfy-models-disk")

@app.function(image=image, volumes={"/models": vol}, timeout=1800)
def download_models():
    print("Downloading FLUX.1 dev GGUF (Q4_K_M)...")
    os.makedirs("/models/gguf", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/gguf/flux1-dev-q4_k_m.gguf",
        "https://huggingface.co/city96/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q4_K_M.gguf"
    ])
    
    print("Downloading T5 XXL Text Encoder...")
    os.makedirs("/models/clip", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/clip/t5xxl_fp8_e4m3fn.safetensors",
        "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors"
    ])

    print("Downloading PuLID Flux V0.9.1...")
    os.makedirs("/models/pulid", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/pulid/pulid_flux_v0.9.1.safetensors",
        "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors"
    ])

    print("Downloading Face YOLOv8m (Impact Pack)...")
    os.makedirs("/models/face_detector", exist_ok=True)
    subprocess.run([
        "curl", "-L", "-o", "/models/face_detector/face_yolov8m.onnx",
        "https://huggingface.co/Bingsu/adetailer/resolve/main/face_yolov8m.onnx"
    ])

    vol.commit()
    print("Download complete. Models are now cached in the Modal volume.")

@app.local_entrypoint()
def main():
    download_models.remote()
