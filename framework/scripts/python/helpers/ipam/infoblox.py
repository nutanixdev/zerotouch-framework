from typing import List, Optional
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.entity import Entity
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class Infoblox(Entity):
    __BASEURL__ = "wapi/v2.12"

    def __init__(self, address, username, password):
        resource_type = self.__BASEURL__
        session = RestAPIUtil(address, user=username, pwd=password)
        super(Infoblox, self).__init__(session=session, resource_type=resource_type)

    def get_host_record(self, fqdn: str):
        """Get host record

        Args:
            fqdn (str): Fully Qualified Domain Name which will be the host record name

        Returns:
            List: Response of get host record
        """
        endpoint = f"record:host?name={fqdn}"
        return self.read(endpoint=endpoint)

    def create_host_record(self, fqdn: str, ip: str):
        """Create Host Record for the given IP

        Args:
            fqdn (str): Fully Qualified domain name which will be the host record name
            ip (str): IP address to create host record for

        Returns:
            (bool, str): (True if successful else False, Error if not successful)
        """
        endpoint = "record:host?_return_as_object=1"
        payload = {"name": fqdn, "ipv4addrs": [{"ipv4addr": ip}]}
        try:
            r = self.create(endpoint=endpoint, data=payload)
            if r.get("result"):
                return True, None
            else:
                return False, r.content
        except Exception as e:
            return False, e

    def check_host_record_exists(self, ip: str) -> bool:
        """Check if host record exists for given ip

        Args:
            ip (str): IP address to check if host record exists

        Returns:
            bool: True if record exists, False otherwise
        """
        endpoint = f"record:host?ipv4addr={ip}"
        response = self.read(endpoint=endpoint)
        return True if response else False

    def create_host_record_with_next_available_ip(self, network: str, fqdn: str, exclude_ip_list: Optional[List] = None):
        """Create a host record for next available IP Address
            Steps:
                1. Check if host record already exists for the given fqdn
                   If Host record does not exists:
                      1. Create a new host record with the given ip
                      2. If IP not provided, reserve a free ip and then create a new host record -> use this API "Add host with next available IP address from a network"
                   If Host record already exists:
                      1. Get the IP and return it
        Args:
            network (str): Network/Subnet where the record will be created with next available IP address
            fqdn (str): Fully qualified domain name
            exclude_ip_list (list, optional): List of IP addresses to exclude from
        """
        host_info = self.get_host_record(fqdn.lower())
        if host_info:
            ip_address = host_info[0]["ipv4addrs"][0]["ipv4addr"]
            logger.warning(f"Host record {fqdn} already exists for IP {ip_address}")
            return ip_address, None
        else:
            exclude_ip_list = exclude_ip_list if exclude_ip_list else []
            endpoint = "record:host?_return_fields%2B=name,ipv4addrs&_return_as_object=1"
            payload = {
                "name": fqdn,
                "ipv4addrs": [
                    {
                        "ipv4addr": {
                            "_object_function": "next_available_ip",
                            "_parameters": {"exclude": exclude_ip_list},
                            "_result_field": "ips",
                            "_object": "network",
                            "_object_parameters": {"network": network}
                        }
                    }
                ]
            }
            try:
                response = self.create(endpoint=endpoint, data=payload)
                return response["result"]["ipv4addrs"][0]["ipv4addr"], None
            except Exception as e:
                return None, f"Could not create host record for next available ip address. Error: {e}"
