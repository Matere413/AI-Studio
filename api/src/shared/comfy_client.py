import json
import urllib.request
import websocket
import uuid


class ComfyUIClient:
    """Client for interacting with a ComfyUI server via WebSocket and HTTP.

    Refactored from legacy api.py to encapsulate ComfyUI connection logic.
    """

    def __init__(self, server_address: str = "127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.ws = None

    def connect(self) -> None:
        """Establish a WebSocket connection to the ComfyUI server."""
        self.ws = websocket.WebSocket()
        self.ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

    def load_payload(self, payload_path: str = "payload.json") -> dict:
        """Load a ComfyUI workflow payload from a JSON file.

        Returns the parsed payload dict.
        """
        with open(payload_path, "r") as f:
            return json.load(f)

    def mutate_prompt(self, payload: dict, prompt: str) -> dict:
        """Mutate the positive prompt text in the payload.

        Returns the modified payload dict.
        """
        if "6" in payload["prompt"] and "inputs" in payload["prompt"]["6"]:
            payload["prompt"]["6"]["inputs"]["text"] = prompt
        return payload

    def send_prompt(self, payload: dict) -> None:
        """Send the workflow payload to the ComfyUI server via HTTP.

        Raises on HTTP errors.
        """
        request_payload = {"prompt": payload["prompt"], "client_id": self.client_id}
        req = urllib.request.Request(
            f"http://{self.server_address}/prompt",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

    def listen_for_completion(self) -> dict:
        """Listen on the WebSocket for the 'executed' completion message.

        Returns the output data from the completion message.
        """
        while True:
            out = self.ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message["type"] == "executed":
                    return message["data"]["output"]

    def close(self) -> None:
        """Close the WebSocket connection."""
        if self.ws:
            self.ws.close()
