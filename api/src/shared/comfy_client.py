import json
import os
import time
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

    def connect(self, timeout_s: float | None = None) -> None:
        """Establish a WebSocket connection to the ComfyUI server.

        Args:
            timeout_s: Optional socket-level timeout for the WebSocket handshake.
        """
        self.ws = websocket.WebSocket()
        connect_kwargs = {}
        if timeout_s is not None:
            connect_kwargs["timeout"] = timeout_s
        self.ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}", **connect_kwargs)

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

    def wait_ready(self, timeout_s: float = 60.0, poll_interval: float = 0.5) -> None:
        """Poll the ComfyUI server until /system_stats responds.

        Raises:
            TimeoutError: If the server does not become ready within ``timeout_s``.
        """
        deadline = time.monotonic() + timeout_s
        url = f"http://{self.server_address}/system_stats"
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=poll_interval) as _:
                    return
            except Exception:
                time.sleep(poll_interval)
        raise TimeoutError(f"ComfyUI not ready after {timeout_s}s")

    def queue_prompt(self, payload: dict, timeout_s: float = 60.0) -> str:
        """Queue a workflow prompt and return the prompt_id assigned by ComfyUI.

        Args:
            timeout_s: Maximum seconds to wait for the HTTP response.

        Raises:
            urllib.error.HTTPError: When ComfyUI returns a non-2xx response.
        """
        import urllib.error
        request_payload = {"prompt": payload["prompt"], "client_id": self.client_id}
        req = urllib.request.Request(
            f"http://{self.server_address}/prompt",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw_resp = resp.read().decode("utf-8")
                try:
                    data = json.loads(raw_resp)
                except json.JSONDecodeError as e:
                    print(f"DEBUG queue_prompt json error: {e} | Raw data: {repr(raw_resp)[:500]}")
                    raise RuntimeError(f"JSON Decode Error in queue_prompt: {raw_resp[:200]}")
            return data["prompt_id"]
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = "No body"
            raise RuntimeError(f"HTTP {e.code}: {e.reason} - Body: {body}")

    def stream_progress(self, prompt_id: str, deadline: float):
        """Yield lifecycle events for a queued prompt until it completes or errors.

        Yields dicts with keys ``event``, ``progress`` and ``message``.  The
        generator exits when the prompt finishes; it raises ``TimeoutError`` if
        ``deadline`` is reached first.

        The WebSocket receive timeout is set before each ``recv()`` so a missing
        server response cannot block past the overall pipeline deadline.
        """
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self.ws.settimeout(remaining)
            raw = self.ws.recv()
            if isinstance(raw, bytes):
                # ComfyUI often sends binary preview images. We shouldn't parse them as JSON.
                continue
            if not isinstance(raw, str):
                continue

            try:
                message = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"DEBUG JSON loads failed in stream_progress. Raw data: {repr(raw)[:500]}")
                raise RuntimeError(f"JSON decode failed in stream_progress: {raw[:200]}")
            msg_type = message.get("type")
            data = message.get("data", {})
            msg_prompt_id = data.get("prompt_id")
            if msg_prompt_id and msg_prompt_id != prompt_id:
                continue

            if msg_type == "progress":
                value = data.get("value", 0)
                max_value = data.get("max", 1) or 1
                progress = min(100, int(value * 100 / max_value))
                yield {
                    "event": "progress",
                    "progress": progress,
                    "message": f"Sampling step {value}/{max_value}",
                }
            elif msg_type == "executing":
                node = data.get("node")
                if node is None:
                    return
                yield {
                    "event": "generating",
                    "progress": 0,
                    "message": f"Executing node {node}",
                }
            elif msg_type == "execution_error":
                error_message = data.get("exception_message") or data.get("error") or "ComfyUI execution failed"
                context_parts = []
                exception_type = data.get("exception_type")
                node_id = data.get("node_id")
                node_type = data.get("node_type")
                if exception_type:
                    context_parts.append(str(exception_type))
                if node_id:
                    context_parts.append(f"node {node_id}")
                if node_type:
                    context_parts.append(str(node_type))
                if context_parts:
                    error_message = f"{error_message} ({', '.join(context_parts)})"
                yield {
                    "event": "error",
                    "progress": 0,
                    "message": error_message,
                    "exception_type": exception_type,
                    "node_type": node_type,
                }
                return
            elif msg_type == "executed":
                # ComfyUI emits per-node executed events before the prompt is fully done.
                continue

        raise TimeoutError("Generation deadline reached")

    def resolve_output_path(self, prompt_id: str, output_dir: str, timeout_s: float = 60.0) -> str:
        """Resolve the first output image path from ComfyUI prompt history.

        The history endpoint returns either ``{"outputs": {...}}`` directly or
        a mapping keyed by ``prompt_id``.  The first ``images`` entry found is
        joined with ``output_dir`` to produce an absolute filesystem path.

        Args:
            timeout_s: Maximum seconds to wait for the HTTP response.

        Raises:
            RuntimeError: If the prompt history contains no image outputs.
        """
        url = f"http://{self.server_address}/history/{prompt_id}"
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            history_text = resp.read().decode("utf-8")
            try:
                history = json.loads(history_text)
            except json.JSONDecodeError as e:
                print(f"DEBUG resolve_output_path json error: {e} | Raw data: {repr(history_text)[:500]}")
                raise RuntimeError(f"JSON Decode Error in history: {history_text[:200]}")

        # DEBUG: Print the raw history
        print(f"DEBUG HISTORY FOR {prompt_id}: {history_text}")

        outputs = history.get("outputs")
        if outputs is None:
            outputs = next(iter(history.values()), {}).get("outputs", {})

        for node_id, node_outputs in outputs.items():
            images = node_outputs.get("images", [])
            if images:
                image = images[0]
                filename = image["filename"]
                subfolder = image.get("subfolder", "")
                if subfolder:
                    return os.path.join(output_dir, subfolder, filename)
                return os.path.join(output_dir, filename)

        raise RuntimeError(f"No image outputs found for prompt {prompt_id}")
