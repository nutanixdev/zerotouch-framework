from typing import Dict
from framework.scripts.python.helpers.v1.genesis import Genesis
from framework.scripts.python.helpers.fc.fc_api_key import FcApiKey
from framework.scripts.python.script import Script
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class GenerateFcApiKey(Script):
    """
    Class that generates Foundation Central API Key
    """
    def __init__(self, data: Dict, **kwargs):
        self.status = False
        self.data = data
        self.alias = data.get('fc_alias_key_name')
        self.pc_session = self.data["pc_session"]
        super(GenerateFcApiKey, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if self.alias:
                genesis = Genesis(self.pc_session)
                fc_api_key = FcApiKey(self.pc_session)
                status, _ = genesis.is_fc_enabled()

                if not status:
                    self.exceptions.append(f"Failed to generate FC API Key. Foundation Central service is not enabled {self.data['pc_ip']!r}")
                    return
                else:
                    # Get list of existing fc_api_key_alias
                    fc_api_key_response = fc_api_key.list()
                    fc_api_key_alias = [fc_api_key["alias"] for fc_api_key in fc_api_key_response]
                    if self.alias in fc_api_key_alias:
                        self.logger.warning(f"SKIP: FC API Key with Alias {self.alias} already exists")
                        return

                # Generate new API Key. There is no taskuuid to monitor, it creates the key immediately
                response = fc_api_key.generate_fc_api_key(alias=self.alias)
                self.logger.info(response)
            else:
                self.exceptions.append("Alias missing. Provide 'alias' to generate FC API key")

        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["GenerateFcApiKey"] = "CAN'T VERIFY"

        fc_api_key = FcApiKey(self.pc_session)
        fc_api_key_response = fc_api_key.list()
        fc_api_key_alias = [fc_api_key["alias"] for fc_api_key in fc_api_key_response]
        if self.alias in fc_api_key_alias:
            self.results["GenerateFcApiKey"] = "PASS"
        else:
            self.results["GenerateFcApiKey"] = "FAIL"
