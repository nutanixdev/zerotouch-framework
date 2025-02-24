from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class TopologyType:
    SINGLE = "single"
    CLUSTER = "cluster"
    ALL = "ALL"
    INSTANCE = "instance"


class DbType:
    ORACLE = "oracle_database"
    POSTGRES = "postgres_database"
    SQLSERVER = "sqlserver_database"
    MARIADB = "mariadb_database"
    MYSQL = "mysql_database"
    MONGODB = "mongodb_database"

    @classmethod
    def cluster_dbs(cls):
        """
        Get all supported db types
        Returns:
          list, all the constants
        """
        return [cls.MONGODB, cls.POSTGRES, cls.SQLSERVER]


class ProfileType:
    SOFTWARE = "Software"
    COMPUTE = "Compute"
    NETWORK = "Network"
    DATABASE_PARAMETER = "Database_Parameter"
    WINDOWS_DOMAIN = "WindowsDomain"


class Profile(NDB):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/profiles"
        super(Profile, self).__init__(session)

    def get_spec(self, params: Optional[Dict] = None, spec: Optional[dict] = None) -> (Optional[Dict], Optional[str]):
        raise NotImplementedError(f"get_spec method is not implemented for {type(self).__name__}")

    def update(
        self,
        data=None,
        endpoint=None,
        query=None,
        timeout=None,
        method="PUT"
    ):
        raise NotImplementedError(f"update method is not implemented for  {type(self).__name__}")

    def delete(
        self,
        uuid=None,
        timeout=None,
        endpoint=None,
        query=None,
    ):
        raise NotImplementedError(f"delete method is not implemented for  {type(self).__name__}")

    def read(
        self,
        uuid=None,
        method="GET",
        data=None,
        headers=None,
        endpoint=None,
        query=None,
        timeout=None,
        entity_type=None,
        custom_filters=None
    ):
        raise NotImplementedError(f"read method is not implemented for  {type(self).__name__}")

    def list(
        self,
        endpoint=None,
        use_base_url=False,
        data=None,
        query=None,
        custom_filters=None,
        timeout=None,
        entity_type=None
    ) -> Union[List, Dict]:
        raise NotImplementedError("list method is not implemented for Auth")

    def upload(
        self,
        source,
        data,
        endpoint="import_file",
        query=None,
        timeout=30,
    ):
        raise NotImplementedError("upload method is not implemented for Auth")

    def create_default_network_profiles(self, vlan_name: str):
        """
        Create the default network profiles for all the DBs
        Args:
          vlan_name(str): The name of the network
        Returns:
          list: API response
        """
        payloads = [
            {
                "name": "DEFAULT_OOB_ORACLE_NETWORK",
                "description":
                    "Default network profile for Oracle created during NDB setup",
                "type": "Network",
                "engineType": "oracle_database",
                "properties": [{"name": "VLAN_NAME", "value": vlan_name}],
                "topology": "single",
                "published": True
            },
            {
                "name": "DEFAULT_OOB_POSTGRESQL_NETWORK",
                "description":
                    "Default network profile for PostgreSQL created during NDB setup",
                "type": "Network",
                "engineType": "postgres_database",
                "properties": [{"name": "VLAN_NAME", "value": vlan_name}],
                "topology": "ALL",
                "published": True
            },
            {
                "name": "DEFAULT_OOB_SQLSERVER_NETWORK",
                "description":
                    "Default network profile for SQLServer created during NDB setup",
                "type": "Network",
                "engineType": "sqlserver_database",
                "properties": [{"name": "VLAN_NAME", "value": vlan_name}],
                "topology": "ALL",
                "published": True
            },
            {
                "name": "DEFAULT_OOB_MARIADB_NETWORK",
                "description":
                    "Default network profile for MariaDB created during NDB setup",
                "type": "Network",
                "engineType": "mariadb_database",
                "properties": [{"name": "VLAN_NAME", "value": vlan_name}],
                "topology": "ALL",
                "published": True
            },
            {
                "name": "DEFAULT_OOB_MYSQL_NETWORK",
                "description":
                    "Default network profile for MySQL created during NDB setup",
                "type": "Network",
                "engineType": "mysql_database",
                "properties": [{"name": "VLAN_NAME", "value": vlan_name}],
                "topology": "ALL",
                "published": True
            },
            {
                "name": "DEFAULT_OOB_MONGODB_NETWORK",
                "description":
                    "Default network profile for MongoDB created during NDB setup",
                "type": "Network",
                "engineType": "mongodb_database",
                "properties": [{"name": "VLAN_NAME", "value": vlan_name}],
                "topology": "ALL",
                "published": True
            }]

        responses = []
        for payload in payloads:
            responses.append(self.create(data=payload))
        return responses

    def create_network_profile(self, engine: str, name: str, vlan_name: str, cluster_id: str,
                               description: str = "", topology: Optional[str] = None,
                               enable_ip_address_selection: bool = False):
        """
        Create network profile
        Args:
          engine(str): The name of database, see DbTyoe
          cluster_id(str): The id of the cluster
          topology(optional str): The topology of the database, see TopologyType
          name(str): The name of the profile
          description(optional str): The description of the profile
          vlan_name(str): The name of the vlan
          enable_ip_address_selection(optional bool): Enable IP address selection
        Returns:
          dict: API response
        """

        data = {
            "name": name,
            "engineType": engine,
            "type": "Network",
            "description": description,
            "topology": topology or TopologyType.ALL,
            "dbVersion": "ALL",
            "systemProfile": False,
            "properties": [{
                "name": "VLAN_NAME",
                "value": vlan_name,
                "secure": False
            },
                {
                    "name": "ENABLE_IP_ADDRESS_SELECTION",
                    "value": enable_ip_address_selection
                }
            ],
            "versionClusterAssociation": [{
                "nxClusterId": cluster_id
            }]
        }
        return self.create(data=data)

    def create_compute_profile(self, name: str, description: Optional[str] = None,
                               topology: Optional[str] = None, num_cpu: str = "1",
                               core_per_cpu: str = "2", memory: str = "16"):
        """
        Create compute profile
        Args:
            topology(optional str): The topology of the database, see TopologyType
            name(str): The name of the profile
            description(optional str): The description of the profile
            num_cpu(str): The number of CPUs
            core_per_cpu(str): The number of cores per CPU
            memory(str): The memory
        Returns:
          dict: API response
        """

        data = {
            "name": name,
            "type": "Compute",
            "description": description,
            "topology": topology or TopologyType.ALL,
            "dbVersion": "ALL",
            "systemProfile": False,
            "properties": [{
                "name": "CPUS",
                "value": num_cpu,
                "secure": False,
                "description": "Number of CPUs in the VM"
            },
                {
                    "name": "CORE_PER_CPU",
                    "value": core_per_cpu,
                    "secure": False,
                    "description": "Number of cores per CPU in the VM"
                },
                {
                    "name": "MEMORY_SIZE",
                    "value": memory,
                    "secure": False,
                    "description": "Total memory (GiB) for the VM"
                }],

        }
        return self.create(data=data)
