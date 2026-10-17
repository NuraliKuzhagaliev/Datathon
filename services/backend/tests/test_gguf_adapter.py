"""Local transport and bounded-image guarantees, without a GPU or private media."""

import base64
from io import BytesIO
import sys
from pathlib import Path
import time

import httpx
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from gguf_model import GGUFModel, image_content
from cashproof.errors import ProcessingError


def test_image_input_is_embedded_bounded_and_keeps_source_pts(tmp_path):
    source = tmp_path / "generated.png"
    Image.new("RGB", (464, 848), "blue").save(source)
    content = image_content(
        [{"id": "actual-frame", "timestamp_sec": 1.234567, "path": source}], 131072, 848
    )
    assert content[0]["text"] == "Frame actual-frame at 1.234567 source seconds"
    uri = content[1]["image_url"]["url"]
    assert uri.startswith("data:image/png;base64,")
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as image:
        assert image.width * image.height <= 131072
    with Image.open(source) as original:
        assert original.size == (464, 848)


def adapter(handler):
    model = GGUFModel.__new__(GGUFModel)
    model.closed = False
    model.process = type("OwnedProcess", (), {"poll": lambda self: None})()
    model.technical_calls = []
    model.runtime_configuration = {
        "max_images_per_call": 16,
        "screening_max_pixels": 131072,
        "verification_max_pixels": 262144,
        "image_max_edge": 848,
        "screening_max_new_tokens": 384,
        "verification_max_new_tokens": 1024,
    }
    model.client = httpx.Client(
        base_url="http://127.0.0.1:12345",
        transport=httpx.MockTransport(handler),
        trust_env=False,
        follow_redirects=False,
    )
    return model


@pytest.mark.parametrize("status", [302, 400, 500])
def test_runtime_errors_never_expose_private_response_body(status):
    model = adapter(
        lambda request: httpx.Response(status, text="PRIVATE_RESPONSE_MUST_STAY_LOCAL")
    )
    try:
        with pytest.raises(ProcessingError) as failure:
            model.infer([], "synthetic", time.time() + 5, {"type": "object"})
        assert "PRIVATE_RESPONSE" not in str(failure.value)
        assert len(model.technical_calls) == 1
    finally:
        model.client.close()


def test_truncated_json_is_a_failure_even_if_parseable():
    model = adapter(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]
            },
        )
    )
    try:
        with pytest.raises(ProcessingError) as failure:
            model.infer([], "synthetic", time.time() + 5)
        assert failure.value.code == "MODEL_OUTPUT_INVALID"
    finally:
        model.client.close()
