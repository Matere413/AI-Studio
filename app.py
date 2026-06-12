import modal

# App de Modal que define la infraestructura y el endpoint
app = modal.App("api-blanca-comfy")

# BLOQUE 1: El Ladrillo (La caja de Docker, pero armada en Python)
comfy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .run_commands(
        "git clone https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
        "pip install -r /root/ComfyUI/requirements.txt",
        "pip install websocket-client fastapi[standard]"  # <--- Agregado acá
    )
)

# BLOQUE 2: El Sótano (Disco virtual para no bajar el modelo de 2GB en cada prendida)
volumen_modelos = modal.Volume.from_name("comfy-models-disk", create_if_missing=True)

# BLOQUE 3: El Portero (La API pública que levanta una GPU de Nvidia barata)
@app.function(image=comfy_image, volumes={"/root/ComfyUI/models": volumen_modelos}, gpu="T4")
@modal.fastapi_endpoint(method="POST")
def generador(pedido: dict):
    # En producción, acá adentro metemos tu script de JSON y WebSockets
    texto_cliente = pedido.get("prompt", "sin prompt")
    return {"estado": "exito", "GPU": "T4 encendida", "pedido": texto_cliente}