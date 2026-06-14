import asyncio
import websockets
import ssl
import json
import urllib.request
import urllib.error
import os

async def run_flow():
    base_url = "matere413--api-blanca-comfy-asgi-app-dev.modal.run"
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    print("🚀 1. Creando Job...")
    req = urllib.request.Request(
        f"https://{base_url}/generate",
        data=json.dumps({
            "prompt": "A realistic chihuahua dog, 4k, masterpiece",
            "checkpoint_url": "epicrealism_naturalSinRC1VAE.safetensors"
        }).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            job_id = data["job_id"]
            print(f"✅ Job creado! ID: {job_id}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ Falló el POST: HTTP Error {e.code}: {e.reason}")
        print(f"❌ Detalles del error: {error_body}")
        return
    except Exception as e:
        print(f"❌ Falló el POST: {e}")
        return

    print("🔌 2. Conectando al WebSocket...")
    uri = f"wss://{base_url}/ws/generate/{job_id}"

    try:
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("🟢 ¡Conectado! Escuchando eventos...")
            while True:
                response = await websocket.recv()
                event_data = json.loads(response)
                event_type = event_data['event']
                
                if event_type == "progress":
                    print(f"⏳ Progreso: {event_data.get('progress')}% - {event_data.get('message')}")
                elif event_type in ["booting_server", "generating", "downloading_weights"]:
                    print(f"⚙️  Estado: {event_type} - {event_data.get('message', '')}")
                elif event_type == "error":
                    print(f"❌ ERROR: {event_data.get('error')}")
                    break
                elif event_type == "completed":
                    print(f"🎉 ¡Terminado! Imagen lista.")
                    # 3. Descargar la imagen
                    image_url = f"https://{base_url}/images/{job_id}"
                    print(f"🖼️  3. Descargando imagen desde: {image_url}")
                    
                    req_img = urllib.request.Request(image_url)
                    with urllib.request.urlopen(req_img, context=ssl_context) as img_response:
                        img_data = img_response.read()
                        out_filename = f"resultado_{job_id}.png"
                        with open(out_filename, "wb") as f:
                            f.write(img_data)
                        print(f"💾 Imagen guardada exitosamente como '{out_filename}'")
                    break
                else:
                    print(f"📩 Evento: {event_type} | Data: {event_data}")
                    
    except websockets.exceptions.ConnectionClosed:
        print("🔴 Conexión cerrada.")

if __name__ == "__main__":
    asyncio.run(run_flow())



