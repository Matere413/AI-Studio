import modal
import os

app = modal.App("sync-models")
vol = modal.Volume.from_name("comfy-models-disk")

download_image = modal.Image.debian_slim(python_version="3.10").pip_install("httpx")

MODELS_TO_DELETE = [
    "checkpoints/epicrealism_naturalSinRC1VAE.safetensors",
    "checkpoints/juggernautXL_ragnarok.safetensors",
    "checkpoints/v1-5-pruned-emaonly-fp16.safetensors",
    "checkpoints/RealVisXL_V4.0.safetensors",
    "loras/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
    "unets/qwen_image_2512_fp8_e4m3fn.safetensors",
    "clip/qwen_2.5_vl_7b_fp8_scaled.safetensors",
    "vae/qwen_image_vae.safetensors",
    "ipadapter/ip-adapter-faceid-plusv2_sdxl.bin",
    "clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
]

MODELS_TO_DOWNLOAD = [
    {
        "url": "https://huggingface.co/black-forest-labs/FLUX.2-dev/resolve/main/flux2_dev_fp8mixed.safetensors",
        "dest": "unets/flux2_dev_fp8mixed.safetensors"
    },
    {
        "url": "https://huggingface.co/black-forest-labs/FLUX.2-dev/resolve/main/vae/full_encoder_small_decoder.safetensors",
        "dest": "vae/full_encoder_small_decoder.safetensors"
    },
    {
        "url": "https://huggingface.co/mistralai/Mistral-3-Small-Flux2/resolve/main/mistral_3_small_flux2_bf16.safetensors",
        "dest": "clip/mistral_3_small_flux2_bf16.safetensors"
    },
    {
        "url": "https://huggingface.co/black-forest-labs/FLUX.2-Turbo-LoRA/resolve/main/Flux_2-Turbo-LoRA_comfyui.safetensors",
        "dest": "loras/Flux_2-Turbo-LoRA_comfyui.safetensors"
    }
]

# Obtenemos el token localmente si existe
hf_token = os.environ.get("HF_TOKEN", "")

@app.function(
    image=download_image,
    volumes={"/models": vol},
    timeout=3600,
    secrets=[modal.Secret.from_dict({"HF_TOKEN": hf_token})] if hf_token else []
)
def sync():
    import httpx
    
    print("🚀 Iniciando limpieza de modelos viejos...")
    for rel_path in MODELS_TO_DELETE:
        full_path = os.path.join("/models", rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            print(f"✅ Eliminado: {rel_path}")
        else:
            print(f"⚠️ No encontrado (ya eliminado): {rel_path}")

    print("\n🚀 Iniciando descarga de modelos Flux 2...")
    
    # Preparamos los headers con el token de HuggingFace si está disponible
    token = os.environ.get("HF_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if not token:
        print("⚠️ ALERTA: No se detectó HF_TOKEN. Si los repositorios son privados o requieren aceptación de licencia, fallará con 401.")

    with httpx.Client(follow_redirects=True, headers=headers) as client:
        for model in MODELS_TO_DOWNLOAD:
            dest_path = os.path.join("/models", model["dest"])
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            if os.path.exists(dest_path):
                print(f"✅ Ya existe, saltando: {model['dest']}")
                continue
                
            print(f"⏳ Descargando {model['dest']}...")
            try:
                with client.stream("GET", model["url"], timeout=300) as response:
                    response.raise_for_status()
                    with open(dest_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                print(f"✅ Descarga completada: {model['dest']}")
            except Exception as e:
                print(f"❌ Error descargando {model['dest']}: {e}")

    vol.commit()
    print("\n🎉 Sincronización finalizada exitosamente.")

@app.local_entrypoint()
def main():
    sync.remote()