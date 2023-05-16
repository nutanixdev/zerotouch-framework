import logging
from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.state_monitor.application_state_monitor import ApplicationStateMonitor
from scripts.python.script import Script
from calm.dsl.cli import create_app
from scripts.python.helpers.v3.application import Application

logger = get_logger(__name__)


class CreateAppFromDsl(Script):
    def __init__(self, data: dict):
        self.data = data

    def execute(self, **kwargs):
        session = RestAPIUtil(self.data["pc_ip"], user=self.data["pc_username"], pwd=self.data["pc_password"],
                              port="9440", secured=True)

        # Get the BPs list
        for bp in self.data["bp_list"]:
            logger.info(f"Creating Blueprint and Launching app {bp['app_name']}")
            bp_file = f"{self.data['project_root']}/{bp['dsl_file']}"
            logging.info(f"Creating app {bp['app_name']} from the blueprint {bp['name']}")
            create_app(
                app_name=bp['app_name'],
                bp_file=bp_file
            )

            # Monitoring application status
            application_op = Application(session)
            application_uuid = application_op.get_uuid_by_name(bp['app_name'])

            if application_uuid:
                logger.info("Application is being provisioned")
                app_response, status = ApplicationStateMonitor(session,
                                                               application_uuid=application_uuid).monitor()
                if not status or not app_response:
                    raise Exception("Application deployment failed")
                else:
                    logger.info("Application deployment successful")
            else:
                logger.warning("Could not fetch application uuid to monitor. Application might or "
                               "might not be running")
                raise Exception("Stopped")

    def verify(self, **kwargs):
        pass
