from src.shared.comfy_client import ComfyUIClient


def main():
    """Example script demonstrating ComfyUIClient usage.

    Connects to a local ComfyUI server, sends a generation request,
    and listens for completion.
    """
    client = ComfyUIClient(server_address="127.0.0.1:8188")
    client.connect()

    try:
        payload = client.load_payload("payload.json")
        payload = client.mutate_prompt(payload, "un gato cyberpunk leyendo un libro")
        client.send_prompt(payload)

        print("Trabajo enviado. Esperando que la Mac termine de cocinar...")
        result = client.listen_for_completion()
        print("¡Bingo! Imagen terminada. Datos:", result)
    finally:
        client.close()


if __name__ == "__main__":
    main()
