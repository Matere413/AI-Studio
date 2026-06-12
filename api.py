import json
import urllib.request
import websocket
import uuid

# Configuración inicial: identificador único y servidor local
# Usamos UUID para distinguir esta sesión de otros clientes
client_id = str(uuid.uuid4())
server_address = "127.0.0.1:8188"

# 2. Levantamos el "teléfono" (WebSocket) antes de pedir nada
ws = websocket.WebSocket()
ws.connect(f"ws://{server_address}/ws?clientId={client_id}")

# 3. Preparamos la plantilla de trabajo
with open("payload.json", "r") as file:
    data = json.load(file)

# Reemplazamos solo el texto del prompt dentro del payload
data["prompt"]["6"]["inputs"]["text"] = "un gato cyberpunk leyendo un libro"

# 4. Armamos el request final con el prompt y el client_id
payload = {"prompt": data["prompt"], "client_id": client_id}
req = urllib.request.Request(
    f"http://{server_address}/prompt", 
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)
# Enviamos el JSON al endpoint de prompts del servidor
urllib.request.urlopen(req)

# 5. Nos quedamos escuchando la transmisión en vivo
print("Trabajo enviado. Esperando que la Mac termine de cocinar...")
while True:
    out = ws.recv()
    if isinstance(out, str):
        message = json.loads(out)
        
        # El servidor nos avisa "executed" cuando un nodo terminó su tarea
        if message['type'] == 'executed':
            print("¡Bingo! Imagen terminada. Datos:", message['data']['output'])
            break # Cortamos la conexión porque ya terminó

ws.close()