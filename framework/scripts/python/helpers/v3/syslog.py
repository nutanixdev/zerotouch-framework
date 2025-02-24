from typing import Optional

from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity


class RemoteSyslog(PcEntity):
    kind = "remote_syslog_server"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/remote_syslog_servers"
        super(RemoteSyslog, self).__init__(session=session)

    def get_payload(self, server_name: str, ip_address: str, port: int, network_protocol: str, module_list: list,
                    spec_version: Optional = None):
        """
        Args:
            server_name(str): The server name
            ip_address(str): The ip address
            port(int): The port number
            network_protocol(str): The protocol, TCP or UDP
            module_list(list): The list of modules - EX: ACROPOLIS,GENESIS,etc
            spec_version(str): While updating we need to give next spec version
        """
        server_name = server_name
        ip_address = ip_address
        port = port
        network_protocol = network_protocol

        payload = {
            "spec": {
                "resources": {
                    "server_name": server_name,
                    "ip_address": ip_address,
                    "port": port,
                    "network_protocol": network_protocol,
                    "module_list": module_list
                }
            },
            "metadata": {
                "kind": self.kind
            },
            "api_version": "3.1.0"
        }

        if spec_version:
            payload["metadata"]["spec_version"] = spec_version

        return payload

    def create_syslog_server(self, server_name: str, ip_address: str, port: int,
                             network_protocol: str, module_list: list) -> dict:
        """
        Create syslog server with give args

        Args:
            server_name(str): The server name
            ip_address(str): The ip address
            port(int): The port number
            network_protocol(str): The protocol, TCP or UDP
            module_list(list): The list of modules - EX: ACROPOLIS,GENESIS,etc


        Returns:
          The json response returned by API.
        """
        return super(RemoteSyslog, self).create(data=self.get_payload(server_name=server_name,
                                                                      ip_address=ip_address,
                                                                      port=port,
                                                                      network_protocol=network_protocol,
                                                                      module_list=module_list))

    def update_syslog_server(self, server_name: str, ip_address: str, port: int,
                             network_protocol: str, module_list: list, uuid: str, spec_version: str) -> dict:
        """
        Update syslog server with give args

        Args:
            server_name(str): The server name
            ip_address(str): The ip address
            port(int): The port number
            network_protocol(str): The protocol, TCP or UDP
            module_list(list): The list of modules - EX: ACROPOLIS,GENESIS,etc
            uuid(str): The uuid of the syslog server to be updated
            spec_version(str): Updating needs a spec version to be provided as input

        Returns:
          The json response returned by API.
        """
        return super(RemoteSyslog, self).update(data=self.get_payload(server_name=server_name,
                                                                      ip_address=ip_address,
                                                                      port=port,
                                                                      network_protocol=network_protocol,
                                                                      module_list=module_list,
                                                                      spec_version=spec_version),
                                                endpoint=uuid)


class RemoteSyslogModule(PcEntity):
    kind = "remote_syslog_module"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/remote_syslog_modules"
        super(RemoteSyslogModule, self).__init__(session=session)

    def create(self, **kwargs) -> dict:
        """
        Creates modules for the rsyslog server that has been configured

        Args:
          kwargs:
            log_level(int): The level of logs to collect 0-4
            modules(list): The list of modules - EX: ACROPOLIS,GENESIS,etc


        Returns:
          The json response returned by API.
        """
        module_list = []

        log_level = kwargs.get("log_level", "0")
        modules = kwargs.get("modules")

        for module in modules:
            module_list.append({
                "module_name": module,
                "log_severity_level": log_level
            })

        payload = {
            "spec": {
                "resources": {
                    "module_list": module_list
                }
            },
            "metadata": {
                "kind": self.kind
            },
            "api_version": "3.1.0"
        }
        return super(RemoteSyslogModule, self).create(data=payload)
