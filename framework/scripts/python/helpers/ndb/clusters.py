import json
from copy import deepcopy
from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class Cluster(NDB):
    AGENT_VM_PREFIX = "EraAgent"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/clusters"
        super(Cluster, self).__init__(session)
        self.build_spec_methods = {}
        self.build_spec_new_register = {
            "name": self._build_spec_name,
            "description": self._build_spec_desc,
            "cluster_ip": self._build_spec_cluster_ip,
            "username": self._build_spec_cluster_username,
            "password": self._build_spec_cluster_password
        }
        self.build_spec_register = {
            "name": self._build_spec_clustername,
            "name_prefix": self._build_spec_name_prefix,
            "cluster_ip": self._build_spec_clusterip,
            "username": self._build_spec_clusterusername,
            "password": self._build_spec_clusterpassword,
            "dns_servers": self._build_spec_dns_servers,
            "ntp_servers": self._build_spec_ntp_servers,
            "agent_vm_ip": self._build_spec_vlan_access,
            "storage_container": self._build_spec_storage_container,
        }
        self.build_spec_update = {
            "name": self._build_spec_name,
            "description": self._build_spec_desc,
            "cluster_ip": self._build_spec_cluster_ip,
            "username": self._build_spec_cluster_username,
            "password": self._build_spec_cluster_password,
            "properties": self._build_spec_properties
        }

    def list(
        self,
        **kwargs
    ) -> Union[List, Dict]:
        return super().read()

    def get_spec(self, params: Optional[Dict] = None, spec: Optional[dict] = None) -> (Optional[Dict], Optional[str]):
        raise NotImplementedError("Method not implemented")

    def get_new_cluster_spec(self, params: Optional[Dict] = None) -> (Optional[Dict], Optional[str]):
        self.build_spec_methods = deepcopy(self.build_spec_new_register)
        spec, error = super().get_spec(params, self._get_default_new_register_spec())
        self.build_spec_methods = {}
        return spec, error

    def get_cluster_spec(self, params: Optional[Dict] = None) -> (Optional[Dict], Optional[str]):
        self.build_spec_methods = deepcopy(self.build_spec_register)
        spec, error = super().get_spec(params)
        self.build_spec_methods = {}
        return spec, error

    def get_update_cluster_spec(self, params: Optional[Dict] = None) -> (Optional[Dict], Optional[str]):
        self.build_spec_methods = deepcopy(self.build_spec_update)
        spec, error = super().get_spec(params, self._get_default_new_register_spec())
        self.build_spec_methods = {}
        return spec, error

    def get_cluster(self, uuid: Optional[str] = None, name: Optional[str] = None):
        if uuid:
            resp = self.read(uuid=uuid)
        elif name:
            endpoint = f"name/{name}"
            resp = self.read(endpoint=endpoint)
        else:
            return (
                None,
                "Please provide either uuid or name for fetching cluster details",
            )

        if isinstance(resp, dict) and resp.get("errorCode"):
            raise Exception(f"Failed fetching cluster info: {resp.get('message')}")

        return resp, None

    @staticmethod
    def _get_default_new_register_spec():
        return deepcopy(
            {
                "name": str,
                "description": "",
                "ipAddresses": list,
                "username": str,
                "password": str,
                "status": "UP",
                "version": "v2",
                "cloudType": "NTNX"
            }
        )

    def _get_default_spec(self):
        return deepcopy(
            {
                "clusterName": str,
                "clusterDescription": "",
                "clusterIP": str,
                "storageContainer": str,
                "agentVMPrefix": self.AGENT_VM_PREFIX,
                "port": 9440,
                "protocol": "https",
                "clusterType": "NTNX",
                "version": "v2",
                "credentialsInfo": [],
                "agentNetworkInfo": [],
                "networksInfo": [],
            }
        )

    @staticmethod
    def _build_spec_name(payload, name, complete_config: dict = None):
        payload["name"] = name
        return payload, None

    @staticmethod
    def _build_spec_clustername(payload, name, complete_config: dict = None):
        payload["clusterName"] = name
        return payload, None

    @staticmethod
    def _build_spec_desc(payload, desc, complete_config: dict = None):
        payload["description"] = desc
        return payload, None

    @staticmethod
    def _build_spec_name_prefix(payload, prefix, complete_config: dict = None):
        payload["agentVMPrefix"] = prefix
        return payload, None

    @staticmethod
    def _build_spec_cluster_ip(payload, cluster_ip, complete_config: dict = None):
        payload["ipAddresses"] = [cluster_ip]
        return payload, None

    @staticmethod
    def _build_spec_clusterip(payload, cluster_ip, complete_config: dict = None):
        payload["clusterIP"] = cluster_ip
        return payload, None

    @staticmethod
    def _build_spec_cluster_username(payload, username, complete_config: dict = None):
        payload["username"] = username
        return payload, None

    @staticmethod
    def _build_spec_cluster_password(payload, password, complete_config: dict = None):
        payload["password"] = password
        return payload, None

    @staticmethod
    def _build_spec_properties(payload, properties, complete_config: dict = None):
        payload["properties"] = payload.get("properties", [])

        for ndb_property in properties:
            payload["properties"].append(ndb_property)
        return payload, None

    @staticmethod
    def _build_spec_clusterusername(payload, username, complete_config: dict = None):
        payload["credentialsInfo"].append({"name": "username", "value": username})
        return payload, None

    @staticmethod
    def _build_spec_clusterpassword(payload, password, complete_config: dict = None):
        payload["credentialsInfo"].append({"name": "password", "value": password})
        return payload, None

    @staticmethod
    def _build_spec_dns_servers(payload, dns_servers: str, complete_config: dict = None):
        payload["agentNetworkInfo"].append(
            {"name": "dns", "value": dns_servers}
        )
        return payload, None

    @staticmethod
    def _build_spec_ntp_servers(payload, ntp_servers: str, complete_config: dict = None):
        payload["agentNetworkInfo"].append(
            {"name": "ntp", "value": ntp_servers}
        )
        return payload, None

    @staticmethod
    def _build_spec_vlan_access(payload, agent_vm_ip, complete_config: dict = None):
        payload["networksInfo"].append({
            "type": "Static",
            "networkInfo": [
                {
                    "name": "vlanName",
                    "value": complete_config["agent_vm_vlan"],
                },
                {
                    "name": "staticIP",
                    "value": agent_vm_ip,
                },
                {
                    "name": "gateway",
                    "value": complete_config["static_networks"][complete_config["agent_vm_vlan"]]["gateway"],
                },
                {
                    "name": "subnetMask",
                    "value": complete_config["static_networks"][complete_config["agent_vm_vlan"]]["netmask"],
                },
            ],
            "accessType": [
                "PRISM",
                "DSIP",
                "DBSERVER"
            ]
        })
        return payload, None

    @staticmethod
    def _build_spec_storage_container(payload, storage_container, complete_config: dict = None):
        payload["storageContainer"] = storage_container
        return payload, None

    def set_cluster_json(self, cluster_id: str, cluster_ip: str,
                         username: str, password: str, skip_upload: str = "false",
                         skip_profile: str = "true", update_json: str = "true"):
        """
        Set the cluster json
        Args:
            cluster_id(str): The id of the cluster
            cluster_ip(str): The ip address of the cluster
            username(str): The username of the cluster
            password(str): The password of the cluster
            skip_upload(str): Whether to skip upload
            skip_profile(str): Whether to skip profile
            update_json(str): Whether to update json
        """
        endpoint = f"{cluster_id}/json"
        query = {
            "skip_upload": skip_upload,
            "skip_profile": skip_profile,
            "updateJson": update_json
        }
        body = {
            "protocol": "https",
            "ip_address": cluster_ip,
            "port": "9440",
            "creds_bag": {
                "username": username,
                "password": password
            }
        }
        files = {
            'file': json.dumps(body).encode()
        }
        return self.upload_json(query=query, endpoint=endpoint, headers={}, files=files)

    def get_cluster_json(self, cluster_id: str):
        endpoint = f"i/{cluster_id}/json"
        return self.read(headers=None, endpoint=endpoint)

    def get_pe_cluster_info(self, cluster_name: str, cluster_ip: str, username: str, password: str):
        endpoint = "i/cluster-info"
        payload = {
            "name": cluster_name,
            "ip": cluster_ip,
            "ipAddresses": [
                cluster_ip
            ],
            "username": username,
            "password": password
        }
        return self.create(endpoint=endpoint, data=payload)

    def enable_multicluster(self, vlan_name: str, agent_vm_prefix: Optional[str] = None):
        """
        Enable the multi cluster support

        Args:
          agent_vm_prefix(optional str): The prefix of the Agent VM
          vlan_name(str): The vlan network for ERA

        Returns:
          dict, API response
          {
            "name": "era_enable_multi_cluster",
            "workId": "b26c2485-9d27-4dbb-b7f0-0c0e3e26bb63",
            "operationId": "6494b65c-2a1a-4579-8c28-a057e1e8963f",
            "dbserverId": "6d2cfeca-b17f-42ce-aa60-fc7c7e1f75fe",
            "entityName": "era_enable_multi_cluster",
            "status": "success"
          }
        """
        prefix = agent_vm_prefix or self.AGENT_VM_PREFIX
        payload = {
            "agentVMPrefix": prefix,
            "vlanName": vlan_name
        }
        return self.create(endpoint="enable-multicluster", data=payload)
