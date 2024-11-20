import logging
import json
import os
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.state_monitor.application_state_monitor import ApplicationStateMonitor
from framework.scripts.python.script import Script
from calm.dsl.cli import launch_blueprint_simple
from framework.scripts.python.helpers.v3.application import Application

logger = get_logger(__name__)


class LaunchBp(Script):
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        super(LaunchBp, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        session = RestAPIUtil(self.data["pc_ip"], user=self.data["pc_username"], pwd=self.data["pc_password"],
                              port="9440", secured=True)

        # Get the BPs list
        for bp in self.data["bp_list"]:
            logging.info(f"Creating app {bp['app_name']} from the blueprint {bp['name']}")

            # open a new file for writing
            with open('launch_params.py', 'w') as f:
                f.write('variable_list = ')
                json.dump(bp['variable_list'], f)
                f.write('\n')

            try:
                launch_blueprint_simple(
                    blueprint_name=bp['name'],
                    app_name=bp['app_name'],
                    launch_params=f"launch_params.py"
                )
            except Exception as e:
                raise e
            finally:
                if 'f' in locals():
                    f.close()
                # Delete the project file
                os.remove(f"launch_params.py")

            # Monitoring application status
            application_op = Application(session)
            application_uuid = application_op.get_uuid_by_name(bp['app_name'])

            if application_uuid:
                self.logger.info("Application is being provisioned")
                app_response, status = ApplicationStateMonitor(session,
                                                               application_uuid=application_uuid).monitor()
                if not status or not app_response:
                    raise Exception("Application deployment failed")
                else:
                    self.logger.info("Application deployment successful")
            else:
                self.logger.warning("Could not fetch application uuid to monitor. Application might or "
                                    "might not be running")
                raise Exception("Stopped")

    def verify(self, **kwargs):
        pass
