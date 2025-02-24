from typing import Dict
from framework.scripts.python.script import Script
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.helpers.fc.update_cvm_foundation import UpdateCvmFoundation as UpdateFoundation

logger = get_logger(__name__)


class UpdateCvmFoundation(Script):
    """
    Update CVM foundation
    """
    def __init__(self, data: Dict):
        self.data = data
        self.foundation_config = self.data["foundation"]
        self.cvm_ips = self.data["cvm_ips"]
        super(UpdateCvmFoundation, self).__init__()
        self.logger = self.logger or logger

    def execute(self):
        try:
            foundation_update_scripts = BatchScript(parallel=True, results_key='CvmFoundationUpdate')
            cvm_user = self.data.get("cvm_credential")
            cred_details = self.data['vaults'][self.data['vault_to_use']]['credentials']
            cvm_username, cvm_password = cred_details.get(cvm_user, {}).get('username'), cred_details.get(cvm_user, {}).get('password')
            if not cvm_username and not cvm_password:
                self.exceptions.append("CVM Credentials are not provided")
                return
            for cvm_ip in self.cvm_ips:
                foundation_update_scripts.add(UpdateFoundation(cvm_ip=cvm_ip, cvm_username=cvm_username,
                                                               cvm_password=cvm_password,
                                                               foundation_url_path=self.foundation_config["foundation_build_url"],
                                                               foundation_version=str(self.foundation_config["foundation_version"]),
                                                               nameserver=self.data.get("nameserver"),
                                                               downgrade=self.data.get("downgrade")))
            result = foundation_update_scripts.run()
            self.logger.info(result)
        except Exception as e:
            self.exceptions.append(f"Exception occured while updating CVM Foundation: {e}")

    def verify(self):
        pass
