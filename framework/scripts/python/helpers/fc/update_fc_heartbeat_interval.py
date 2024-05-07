import logging
from framework.scripts.python.script import Script
from framework.helpers.log_utils import get_logger
from ..ssh_cvm import SSHCVM

logger = get_logger(__name__)


class UpdateFCHeartbeatInterval(Script):
    """
    Update FC heartbeat interval
    """
    def __init__(self, cvm_ip: str, cvm_username: str, cvm_password: str, interval_min: int, fc_deployment_logger: logging.getLogger = None):
        """
        Args:
            cvm_ip (str): CVM IP
            cvm_username (str): CVM username
            cvm_password (str): CVM password
            fc_deployment_logger (Object, optional): Logger object to be used to log the output
        """
        self.cvm_ip = cvm_ip
        self.interval_min = interval_min
        super(UpdateFCHeartbeatInterval, self).__init__()
        self.logger = fc_deployment_logger or logger
        self.ssh_cvm = SSHCVM(cvm_ip, cvm_username, cvm_password)

    def execute(self):
        status, error_message = self.ssh_cvm.update_heartbeat_interval_mins(self.interval_min)
        self.results = {"cvm_ip": self.cvm_ip, "status": status, "error": error_message}
        self.logger.debug(self.results)

    def verify(self):
        pass
