from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class Config(NDB):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/config"
        super(Config, self).__init__(session)

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
        query=None,
        data=None,
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

    def get_cluster_config(self, uuid: str):
        """
        Get era server config
        Args:
          uuid(str): The uuid of the cluster
        Returns:
          dict: The cluster info
        """
        endpoint = f"era-server/{uuid}"
        return super().read(endpoint=endpoint)

    def update_dns(self, config: dict):
        """
        Update DNS
        Args:
          config(dict): Era config
        Returns:
          API response
        """
        return self._update_config(config, "dns")

    def update_ntp(self, config: dict):
        """
        Update NTP
        Args:
          config(dict): Era config
        Returns:
          API response
        """
        return self._update_config(config, "ntp")

    def update_timezone(self, config: dict):
        """
        Update Timezone
        Args:
          config(dict): Era config
        Returns:
          API response
        """
        return self._update_config(config, "timezone")

    def update_smtp(self, config: dict):
        """
        Update SMTP
        Args:
          config(dict): Era config
        Returns:
          API response
        """
        return self._update_config(config, "smtp")

    def _update_config(self, config: dict, config_params: str):
        """
        Update ERA config
        Args:
          config(dict): The era config
          config_params(str): param, for example, dns, ntp, smtp, timezone

        Returns:
          dict: API response, for example:
          {
            "dnsServers": ["10.40.64.15", "10.40.64.16"],
            "ntpServers": ["0.centos.pool.ntp.org",
                           "1.centos.pool.ntp.org",
                           "2.centos.pool.ntp.org",
                           "3.centos.pool.ntp.org"],
            "smtpConfig": {
              "smtpServerIPPort": None,
              "smtpUsername": None,
              "smtpPassword": None,
              "isSmtpPasswordChanged": false,
              "emailFromAddress": None,
              "tlsEnabled": false,
              "testEmailToAddress": None,
              "slackAPIURL": None,
              "unsecured": False
            },
            "timezone": "America/Los_Angeles"
          }

        """
        endpoint = "era-server"
        query = {
            "config-params": config_params
        }
        return super().update(data=config, endpoint=endpoint, query=query)
