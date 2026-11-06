"""
FC Image Upload Helper

Uploads image payloads to Foundation Central (FC 2.x) against an
image record that already exists.

Two-step flow, both v1:
1. Upload metadata JSON:
   POST /api/v1/foundation-central/images/{image_extId}/$action/upload-metadata
   Content-Type: application/octet-stream

2. Upload image binary:
   POST /api/v1/foundation-central/images/{image_extId}/$action/upload-image
   Content-Type: application/octet-stream

Creating the image record itself is *not* part of this helper: ``image_extId``
is a required input. Create the record with the v4 ``fc_image`` entity (POST
/api/lifecycle/v4.x/config/images) and pass its extId in, e.g. via
``{fc_image_resource.extId}``. Note that ``helper_schema`` in entity_map.py
marks ``image_extId`` optional, so generated examples emit it commented out;
apply still fails without it. Either upload step may be omitted by leaving
``metadata_path`` / ``image_path`` unset, but at least one is required.

Uses RestAPIUtil with binary streaming (jsonify=False) for large file uploads.
The domain-scoped ``session`` passed at construction already targets the FC
host (see ``EntityHandler._build_rest_session``), so this helper does not
take a separate ``fc_ip`` or ``fc_credential``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.utils.utils import get_logger

FC_IMAGES_V1_PATH = "api/v1/foundation-central/images"
FC_IMAGES_V4_PATH = "api/lifecycle/v4.4/config/images"


class FcImageUploadHelper(PeEntityV1):
    """
    Helper for uploading AOS/AHV image payloads to Foundation Central.

    Uploads metadata (v1) and/or the image binary (v1) against an existing
    image record, whose ``image_extId`` is a required input. See the module
    docstring for how to create that record.
    """

    resource_type = "foundation-central/images"

    def __init__(
        self,
        session: RestAPIUtil,
        proxy_cluster_uuid: str | None = None,
        logger=None,
        data: dict | None = None,
    ):
        self.logger = logger if logger else get_logger(__name__)
        self.data = data or {}
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def _upload_metadata(self, image_ext_id: str, metadata_path: str) -> dict:
        """Upload metadata JSON to FC via v1 API."""
        url = f"{FC_IMAGES_V1_PATH}/{image_ext_id}/$action/upload-metadata"

        meta_path = Path(metadata_path)
        if not meta_path.is_file():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        self.logger.info(f"Uploading metadata for image {image_ext_id}")

        with open(meta_path, "rb") as f:
            metadata_bytes = f.read()

        headers = {"Content-Type": "application/octet-stream"}
        resp = self.session.post(
            url,
            headers=headers,
            data=metadata_bytes,
            jsonify=False,
            verify=False,
        )

        self.logger.info(f"Metadata uploaded for image {image_ext_id}")
        if isinstance(resp, dict):
            return resp
        return {"status": "ok"}

    def _upload_image(self, image_ext_id: str, image_path: str) -> dict:
        """Upload image binary to FC via v1 API (streamed)."""
        url = f"{FC_IMAGES_V1_PATH}/{image_ext_id}/$action/upload-image"

        img_path = Path(image_path)
        if not img_path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        file_size_gb = img_path.stat().st_size / (1024**3)
        self.logger.info(
            f"Uploading image binary for {image_ext_id} ({file_size_gb:.2f} GB)"
        )

        with open(img_path, "rb") as f:
            headers = {"Content-Type": "application/octet-stream"}
            resp = self.session.post(
                url,
                headers=headers,
                data=f,
                jsonify=False,
                verify=False,
            )

        self.logger.info(f"Image binary uploaded for {image_ext_id}")
        if isinstance(resp, dict):
            return resp
        return {"status": "ok"}

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Upload an AOS/AHV image payload to an existing FC image record.

        Uploads metadata JSON via v1, then the image binary via v1. Each
        step runs only if its path is supplied, so this can upload metadata
        only, binary only, or both -- but at least one is required.

        Expected entity_data::

            {
                "image_extId": "uuid-of-existing-image",  # REQUIRED
                "metadata_path": "/path/to/metadata.json",  # at least one
                "image_path": "/path/to/image.iso"          # of the two
            }

        The image record is not created here; ``image_extId`` must already
        exist (see the module docstring). Host, username, and password come
        from the domain session, not the body.

        :return: image_extId as ext_id
        :raises ValueError: If ``image_extId`` is missing, or neither
            ``metadata_path`` nor ``image_path`` is supplied.
        :raises FileNotFoundError: If a supplied path is not a file.
        """
        metadata_path = entity_data.get("metadata_path")
        image_path = entity_data.get("image_path")

        if not metadata_path and not image_path:
            raise ValueError(
                "entity_data must contain at least one of "
                "'metadata_path' or 'image_path'"
            )

        image_ext_id = entity_data.get("image_extId")
        if not image_ext_id:
            raise ValueError("image_extId is required")

        if metadata_path:
            self._upload_metadata(image_ext_id, metadata_path)

        if image_path:
            self._upload_image(image_ext_id, image_path)

        self.logger.info(f"FC image upload complete: {image_ext_id}")
        return image_ext_id

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update is not supported for FC image upload")

    def delete_entity(self, ext_id: str, **kwargs) -> bool:
        """Delete an image from Foundation Central."""
        url = f"{FC_IMAGES_V1_PATH}/{ext_id}"
        self.logger.info(f"Deleting FC image {ext_id}")

        try:
            self.session.delete(url, verify=False)
            self.logger.info(f"FC image {ext_id} deleted")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete FC image {ext_id}: {e}")
            return False

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """List images on Foundation Central."""
        try:
            resp = self.session.get(FC_IMAGES_V4_PATH, verify=False)
            if isinstance(resp, dict):
                data = resp.get("data", [])
                return data if isinstance(data, list) else []
            return []
        except Exception as e:
            self.logger.error(f"List images failed: {e}")
            return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Get an FC image by UUID."""
        try:
            resp = self.session.get(f"{FC_IMAGES_V1_PATH}/{ext_id}")
            if isinstance(resp, dict):
                return resp
            return None
        except Exception as e:
            self.logger.error(f"Failed to get FC image {ext_id}: {e}")
            return None
