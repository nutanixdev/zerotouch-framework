from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1
from ..v1.storage_pool import StoragePool


class Container(PeEntityV1):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/containers"
        self.session = session
        super(Container, self).__init__(session=session)

    def create(self, **kwargs) -> Dict:
        data = self.get_json_for_create(**kwargs)
        return super(Container, self).create(data=data)

    def get_json_for_create(self, **kwargs) -> Dict:
        """
        Helper function to generate container config spec(json) for creation.

        Args:
          kwargs(dict):
            name(str): the name to container.
            storage_pool_uuid(str,optional): The uuid of the storage pool.
            advertised_capacity(int, optional): The advertised capacity of the
              container.
            replication_factor(int, optional): The replication factor value.
            compression_enabled(bool, optional): enable compression or not.
            compression_delay_in_secs(int, optional): compression delay in seconds.
            erasure_code(str,optional): Turn on erasure code or not. Default value
              is OFF.
            finger_print_on_write(str, optional): Turn on dedup or not. Default
              value is OFF.
            on_disk_dedup(str, optional): Turn on disk dedup or not. Default
              value is OFF.

        Returns:
          dict: The container config spec for creation.

        Raises:
          ValueError exception will be raised when no storage pool was found.
        """
        name = kwargs.pop("name")
        storage_pool_uuid = kwargs.pop("storage_pool_uuid", None)
        reserved_in_gb = kwargs.pop("reserved_in_gb", 0)
        advertised_capacity = kwargs.pop("advertisedCapacity_in_gb", None)
        replication_factor = kwargs.pop("replication_factor", None)
        compression_enabled = kwargs.pop("compression_enabled", True)
        compression_delay_in_secs = kwargs.pop("compression_delay_in_secs", 0)
        enable_software_encryption = kwargs.pop("enable_software_encryption", False)
        erasure_code = kwargs.pop("erasure_code", "OFF")
        finger_print_on_write = kwargs.pop("finger_print_on_write", "OFF")
        on_disk_dedup = kwargs.pop("on_disk_dedup", "OFF")
        affinity_host_uuid = kwargs.pop("affinity_host_uuid", None)

        if not storage_pool_uuid:
            storage_pool_list = StoragePool(self.session).read()
            if not storage_pool_list:
                raise ValueError("No storage pools found!")
            else:
                storage_pool_uuid = storage_pool_list[0].get("storagePoolUuid")

        json = {
            "name": name,
            "storagePoolUuid": storage_pool_uuid,
            "totalExplicitReservedCapacity": int(reserved_in_gb) * 1024 * 1024 * 1024,
            "advertisedCapacity": int(advertised_capacity) * 1024 * 1024 * 1024 if advertised_capacity else None,
            "compressionEnabled": compression_enabled,
            "compressionDelayInSecs": compression_delay_in_secs,
            "erasureCode": erasure_code,
            "fingerPrintOnWrite": finger_print_on_write,
            "onDiskDedup": on_disk_dedup,
            "nfsWhitelistAddress": []
        }

        if enable_software_encryption:
            json["enableSoftwareEncryption"] = enable_software_encryption

        if replication_factor:
            json["replicationFactor"] = str(replication_factor)

        if affinity_host_uuid:
            json["affinityHostUuid"] = affinity_host_uuid

        return json
