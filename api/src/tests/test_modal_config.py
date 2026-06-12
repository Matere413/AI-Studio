from src.shared.modal_config import modal_app, comfy_image, model_volume


def test_modal_app_defined():
    """GIVEN the modal_config module
    WHEN importing modal_app
    THEN it is a valid modal App instance.
    """
    assert modal_app is not None
    assert modal_app.name == "api-blanca-comfy"


def test_comfy_image_defined():
    """GIVEN the modal_config module
    WHEN importing comfy_image
    THEN it is a valid modal Image instance.
    """
    assert comfy_image is not None


def test_model_volume_defined():
    """GIVEN the modal_config module
    WHEN importing model_volume
    THEN it is a valid modal Volume instance.
    """
    assert model_volume is not None
