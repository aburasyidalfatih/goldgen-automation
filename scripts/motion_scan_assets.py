"""Register existing generated images for Motion Studio reuse."""

from core.config import IMAGES_DIR
from core.motion_assets import init_asset_storage, scan_existing_images
from core.motion_studio import init_motion_storage


if __name__ == "__main__":
    init_motion_storage()
    init_asset_storage()
    ids = scan_existing_images(IMAGES_DIR)
    print(f"Registered {len(ids)} existing image assets for Motion Studio.")
