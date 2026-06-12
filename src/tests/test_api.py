import pytest
from unittest.mock import patch, MagicMock


def test_api_script_uses_comfy_client():
    """GIVEN api.py main is executed
    WHEN it runs
    THEN it uses ComfyUIClient instead of global state.
    """
    with patch("src.shared.comfy_client.ComfyUIClient") as MockClient:
        instance = MagicMock()
        instance.listen_for_completion.return_value = "image.png"
        MockClient.return_value = instance

        # Import and run main
        import api as api_module
        api_module.main()

        MockClient.assert_called_once_with(server_address="127.0.0.1:8188")
        instance.connect.assert_called_once()
        instance.load_payload.assert_called_once_with("payload.json")
        instance.mutate_prompt.assert_called_once()
        instance.send_prompt.assert_called_once()
        instance.listen_for_completion.assert_called_once()
        instance.close.assert_called_once()
