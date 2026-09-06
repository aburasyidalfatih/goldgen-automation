import json
import base64
import os
import wave
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.motion_qa import validate_render
from core.motion_renderer import default_manifest, render_manifest, write_srt
from core.motion_assets import init_asset_storage, register_asset, search_assets, search_openverse
from core.motion_tts import generate_voiceover
from core.motion_publisher import publish_video


class MotionStudioTests(unittest.TestCase):
    def test_manifest_contains_portrait_contract_and_overlays(self):
        manifest = default_manifest({
            "headline": "GOLD VS PYRITE",
            "list_points": ["Use observation and testing"],
        })
        self.assertEqual((manifest["width"], manifest["height"]), (1080, 1920))
        self.assertEqual(manifest["duration"], 60.0)
        self.assertGreaterEqual(len(manifest["scenes"]), 3)
        self.assertTrue(any(layer["type"] == "arrow"
                            for scene in manifest["scenes"]
                            for layer in scene["layers"]))
        self.assertGreaterEqual(len({scene["motion"] for scene in manifest["scenes"]}), 3)

    def test_srt_uses_scene_text_and_timing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("core.motion_renderer.MOTION_RENDERS_DIR", Path(temp_dir)):
                path = write_srt("test-job", {
                    "scenes": [{"duration": 5, "layers": [{"type": "text", "text": "Observe"}]}]
                })
            content = path.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:05,000", content)
            self.assertIn("Observe", content)

    def test_qa_rejects_missing_render(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = validate_render(root / "missing.mp4", root / "missing.manifest.json")
            self.assertFalse(result["ok"])
            self.assertTrue(result["errors"])

    def test_tts_missing_key_fails_safe(self):
        with patch.dict("os.environ", {}, clear=True), patch("core.motion_tts.CONFIG_PATH", Path("missing-config.json")):
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                generate_voiceover("test-job", "Hello GoldGen")

    def test_tts_interactions_response_is_written_as_wav(self):
        class FakeAudio:
            data = base64.b64encode(b"\x00\x00" * 240).decode("ascii")

        class FakeInteraction:
            output_audio = FakeAudio()

        class FakeInteractions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeInteraction()

        class FakeClient:
            interactions = FakeInteractions()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
                with patch("google.genai.Client", return_value=FakeClient()):
                    with patch("core.motion_tts.MOTION_RENDERS_DIR", Path(temp_dir)):
                        output = generate_voiceover("tts-test", "Hello GoldGen")
            with wave.open(output, "rb") as audio:
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getframerate(), 24000)
                self.assertGreater(audio.getnframes(), 0)

    def test_asset_registry_keeps_source_and_searches_tags(self):
        fixture = Path(__file__).parent / "fixtures" / "motion_background.svg"
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("core.motion_assets.ASSET_DB_PATH", Path(temp_dir) / "assets.db"):
                with patch("core.motion_assets.MOTION_ASSETS_DIR", Path(temp_dir)):
                    init_asset_storage()
                    asset_id = register_asset(fixture, tags=("gold", "background"), status="approved")
                    assets = search_assets("background", approved_only=True)
        self.assertEqual(len(asset_id), 16)
        self.assertEqual(assets[0]["source_path"], str(fixture.resolve()))

    def test_renderer_accepts_scene_background_asset(self):
        fixture = Path(__file__).parent / "fixtures" / "motion_background.svg"
        with tempfile.TemporaryDirectory() as temp_dir:
            render_dir = Path(temp_dir)
            manifest = {
                "width": 1080, "height": 1920, "fps": 30,
                "scenes": [{"duration": 1, "background": str(fixture),
                             "layers": [{"type": "text", "text": "GoldGen"}]}]
            }
            with patch("core.motion_renderer.MOTION_RENDERS_DIR", render_dir):
                result = render_manifest("asset-test", manifest)
            self.assertTrue(Path(result["output_path"]).is_file())

    def test_publisher_is_disabled_by_default(self):
        with patch.dict("os.environ", {"MOTION_AUTO_PUBLISH_ENABLED": "false"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                publish_video("page", "token", "missing.mp4", "caption")

    def test_openverse_search_normalizes_license_metadata(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({"results": [{"id": "1", "title": "River", "url": "https://upload.wikimedia.org/river.jpg", "creator": "A", "license": "by", "license_version": "4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"}]}).encode()
        with patch("core.motion_assets.urlopen", return_value=FakeResponse()):
            result = search_openverse("gold river")
        self.assertEqual(result[0]["license"], "by")
        self.assertEqual(result[0]["creator"], "A")


if __name__ == "__main__":
    unittest.main()
