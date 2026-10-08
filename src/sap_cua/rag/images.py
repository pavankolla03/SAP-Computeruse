"""Tenant-scoped visual memory. Only verified, approved, masked captures are retained."""

import hashlib
import io
import os
from pathlib import Path

from PIL import ImageDraw

from sap_cua.security import sanitize_data


class ScreenshotMemory:
    def __init__(self, store, embeddings, root):
        self.store, self.embeddings, self.root = store, embeddings, Path(root)

    def record(self, image, scope, *, page, module, metadata, verified, approved, mask_boxes=()):
        if scope.role == "viewer":
            raise PermissionError("Viewer cannot record visual memory")
        if verified is not True or approved is not True:
            raise ValueError("Verified execution and approved screenshot capture are required")
        if image.width * image.height > 20_000_000:
            raise ValueError("Screenshot too large")
        image = image.convert("RGB").copy()
        draw = ImageDraw.Draw(image)
        for box in mask_boxes:
            if (
                len(box) != 4
                or box[0] < 0
                or box[1] < 0
                or box[2] > image.width
                or box[3] > image.height
                or box[2] <= box[0]
                or box[3] <= box[1]
            ):
                raise ValueError("Invalid masking region")
            draw.rectangle(box, fill="black")
        # Re-encoding drops source EXIF and all original image metadata.
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data = buffer.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        directory = self.root / scope.customer / scope.tenant
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (digest + ".png")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        vector = self.embeddings.embed([str(path)])[0]
        safe = sanitize_data(
            {
                **metadata,
                "sha256": digest,
                "verified": True,
                "mask_count": len(mask_boxes),
                "artifact": str(path.relative_to(self.root)),
            }
        )
        self.store.put_screenshot(
            digest, scope, page, module, self.embeddings.version, vector, safe
        )
        return safe

    def search(self, path, scope, *, page, module, limit=5):
        if not 1 <= limit <= 10:
            raise ValueError("Invalid screenshot result limit")
        vector = self.embeddings.embed([str(path)])[0]
        return self.store.search_screenshots(
            scope, page, module, self.embeddings.version, vector, limit
        )
