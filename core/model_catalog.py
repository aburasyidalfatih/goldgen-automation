"""Supported Gemini model catalog and safe legacy migrations."""

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"

IMAGE_MODELS = {
    "gemini-3.1-flash-image": "Nano Banana 2 (Gemini 3.1 Flash)",
    "gemini-3.1-flash-lite-image": "Nano Banana 2 Lite (Gemini 3.1 Flash Lite)",
    "gemini-3-pro-image": "Nano Banana Pro (Gemini 3 Pro)",
}

IMAGE_MODEL_SIZES = {
    # Flash Lite only accepts 1K. The other supported models use 2K so text
    # and small infographic details remain readable on Facebook.
    "gemini-3.1-flash-lite-image": "1K",
    "gemini-3.1-flash-image": "2K",
    "gemini-3-pro-image": "2K",
}

# Imagen 4 was retired. Keep this mapping so an older config cannot break the
# next scheduled post after the application is upgraded.
LEGACY_IMAGE_MODELS = {
    "imagen-4": DEFAULT_IMAGE_MODEL,
    "imagen-4.0-generate-001": DEFAULT_IMAGE_MODEL,
    "imagen-4.0-fast-generate-001": DEFAULT_IMAGE_MODEL,
    "imagen-4.0-ultra-generate-001": DEFAULT_IMAGE_MODEL,
}


def normalize_image_model(value):
    """Return a supported model, migrating known retired model identifiers."""
    model = str(value or "").strip()
    if not model:
        return DEFAULT_IMAGE_MODEL
    return LEGACY_IMAGE_MODELS.get(model, model)


def is_supported_image_model(value):
    return normalize_image_model(value) in IMAGE_MODELS


def image_size_for_model(value):
    """Return a resolution accepted by the selected image model."""
    model = normalize_image_model(value)
    return IMAGE_MODEL_SIZES.get(model, "1K")
