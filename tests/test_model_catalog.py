import unittest

from core.model_catalog import (
    DEFAULT_IMAGE_MODEL,
    IMAGE_MODELS,
    image_size_for_model,
    is_supported_image_model,
    normalize_image_model,
)


class ModelCatalogTests(unittest.TestCase):
    def test_current_models_are_available(self):
        self.assertIn("gemini-3.1-flash-image", IMAGE_MODELS)
        self.assertIn("gemini-3.1-flash-lite-image", IMAGE_MODELS)
        self.assertIn("gemini-3-pro-image", IMAGE_MODELS)

    def test_retired_imagen_model_migrates_to_default(self):
        self.assertEqual(DEFAULT_IMAGE_MODEL, normalize_image_model("imagen-4"))
        self.assertTrue(is_supported_image_model("imagen-4"))

    def test_unknown_model_is_not_accepted(self):
        self.assertFalse(is_supported_image_model("made-up-model"))

    def test_resolution_matches_model_capability(self):
        self.assertEqual("1K", image_size_for_model("gemini-3.1-flash-lite-image"))
        self.assertEqual("2K", image_size_for_model("gemini-3.1-flash-image"))
        self.assertEqual("2K", image_size_for_model("gemini-3-pro-image"))


if __name__ == "__main__":
    unittest.main()
