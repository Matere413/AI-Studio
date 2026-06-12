import asyncio
import websockets
import ssl
import json
import urllib.request

async def run_flow():
    base_url = "matere413--api-blanca-comfy-asgi-app-dev.modal.run"
    
    # Creamos un contexto SSL que ignora la verificación (para el POST y el WebSocket)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # 1. Hacemos el POST para crear el Job
    print("🚀 1. Creando Job...")
    req = urllib.request.Request(
        f"https://{base_url}/generate",
        data=json.dumps({
            "prompt": "A futuristic cybernetic studio, neon lights, 4k, masterpiece",
            "checkpoint_url": "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
        }).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        # Le pasamos el context de SSL acá también
        with urllib.request.urlopen(req, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            job_id = data["job_id"]
            print(f"✅ Job creado! ID: {job_id}")
    except Exception as e:
        print(f"❌ Falló el POST: {e}")
        return

    # 2. Nos conectamos al WebSocket
    print("🔌 2. Conectando al WebSocket...")
    uri = f"wss://{base_url}/ws/generate/{job_id}"

    try:
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("🟢 ¡Conectado!")
            while True:
                response = await websocket.recv()
                event_data = json.loads(response)
                print(f"📩 Evento: {event_data['event']} | Data: {event_data}")
    except websockets.exceptions.ConnectionClosed:
        print("🔴 Conexión cerrada (Flujo terminado).")

asyncio.run(run_flow())
