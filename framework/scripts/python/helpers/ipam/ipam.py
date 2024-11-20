from typing import Dict, List
from framework.scripts.python.helpers.ipam.infoblox import Infoblox


class IPMAMapping:
    """
    The class to define IPAM vendors mapping
    """
    IPAM_VENDOR_MAPPING = {
        "infoblox": Infoblox
        }


class IPAM:

    def __init__(self, vendor: str, ipam_address: str, username: str, password: str) -> None:
        self.ipam_obj = self.get_ipam_obj(vendor, ipam_address, username, password)
        if isinstance(self.ipam_obj, str):
            raise Exception(self.ipam_obj)

    def get_ipam_obj(self, vendor: str, ipam_address: str, username: str, password: str):
        """Get IPAM Object for the given vendor

        Args:
            vendor (str): Vendor to use for IPAM functionality
            ipam_address: Address of IPAM used
            username: IPAM username
            password: IPAM password

        Returns:
            Object: IPAM object for the given vendor
        """
        try:
            return IPMAMapping.IPAM_VENDOR_MAPPING[vendor](address=ipam_address,
                                                           username=username,
                                                           password=password)
        except Exception as e:
            return f"Failed to create IPAM object. Error: {e}"

    def create_host_record_with_next_available_ip(self, network: str, fqdn: str, exclude_ip_list: List = []):
        return self.ipam_obj.create_host_record_with_next_available_ip(network, fqdn, exclude_ip_list)

    def check_host_record_exists(self, ip: str):
        return self.ipam_obj.check_host_record_exists(ip)

    def get_host_record(self, fqdn: str):
        return self.ipam_obj.get_host_record(fqdn)

    def create_host_record(self, fqdn: str, ip: str):
        return self.ipam_obj.create_host_record(fqdn, ip)
