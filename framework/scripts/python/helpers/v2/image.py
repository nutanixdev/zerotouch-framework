from copy import deepcopy
from typing import Optional

from ..pe_entity_v2 import PeEntityV2
from framework.helpers.rest_utils import RestAPIUtil


class Image(PeEntityV2):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/images"
        self.session = session
        super(Image, self).__init__(session=session)
        self.build_spec_methods = {
            "name": self._build_spec_name,
            "url": self._build_spec_url,
            "image_type": self._build_spec_image_type,
            "annotation": self._build_spec_annotation,
            "container_name": self._build_spec_container_name
        }

    @staticmethod
    def _build_spec_name(payload: dict, name: str, complete_config: dict = None) -> (dict, None):
        payload["name"] = name
        return payload, None

    @staticmethod
    def _build_spec_url(payload: dict, url: str, complete_config: dict = None) -> (dict, None):
        payload["image_import_spec"]["url"] = url
        return payload, None

    @staticmethod
    def _build_spec_image_type(payload: dict, image_type: str, complete_config: dict = None) -> (dict, None):
        payload["image_type"] = image_type
        return payload, None

    @staticmethod
    def _build_spec_annotation(payload: dict, annotation: str, complete_config: dict = None) -> (dict, None):
        payload["annotation"] = annotation
        return payload, None

    @staticmethod
    def _build_spec_container_name(payload: dict, container_name: str, complete_config: dict = None) -> (dict, None):
        payload["image_import_spec"]["container_name"] = container_name
        return payload, None

    @staticmethod
    def _get_default_spec():
        return deepcopy(
            {
                'image_import_spec': {
                    'url': str,
                    'container_name': str
                },
                'image_type': str,
                'name': str
            }
        )

    def get_vm_disk_info_by_name(self, name: str) -> dict:
        resp = self.read()
        for image in resp:
            if image.get("name") == name:
                return image
        raise ValueError(f"Image with name {name} not found!")

    def get_vm_disk_id(self, name: Optional[str] = None, vm_disk_info: Optional[dict] = None) -> str:
        if not vm_disk_info:
            if not name:
                raise ValueError("Either name or vm_disk_info should be provided!")
            resp = self.read()
            for image in resp:
                if image.get("name") == name:
                    vm_disk_info = image
                    break
            else:
                raise ValueError(f"Image with name {name} not found!")
        return vm_disk_info["vm_disk_id"]

    def get_vm_disk_size(self, name: Optional[str] = None, vm_disk_info: Optional[dict] = None) -> int:
        if not vm_disk_info:
            if not name:
                raise ValueError("Either name or vm_disk_info should be provided!")
            resp = self.read()
            for image in resp:
                if image.get("name") == name:
                    vm_disk_info = image
                    break
            else:
                raise ValueError(f"Image with name {name} not found!")
        return vm_disk_info["vm_disk_size"]
