import logging
from framework.scripts.python.script import Script
from framework.helpers.log_utils import get_logger
from ..cvm.ssh_cvm import SSHCvm

logger = get_logger(__name__)


class EnableOneNode(Script):
    """
    Enable One node support in CVM
    """
    def __init__(self, cvm_ip: str, cvm_username: str, cvm_password: str, fc_deployment_logger: logging.getLogger = None):
        """
        Args:
            cvm_ip (str): CVM IP
            cvm_username (str): CVM username
            cvm_password (str): CVM password
            fc_deployment_logger (Object, optional): Logger object to be used to log the output
        """
        self.cvm_ip = cvm_ip
        super(EnableOneNode, self).__init__()
        self.logger = fc_deployment_logger or logger
        self.ssh_cvm = SSHCvm(cvm_ip, cvm_username, cvm_password)

    def execute(self):
        status, error_message = self.ssh_cvm.enable_one_node()
        self.results = {"cvm_ip": self.cvm_ip, "status": status, "error": error_message}
        self.logger.debug(self.results)

    def verify(self):
        pass
