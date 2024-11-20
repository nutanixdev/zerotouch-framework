import multiprocessing
import concurrent.futures
from typing import Dict
from calm.dsl.api import get_api_client
from calm.dsl.cli import create_user
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateNcmUser(Script):
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.users = self.data["ncm_users"]
        super(CreateNcmUser, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def create_user_template(self, user: Dict):
        try:
            create_user(user["name"], user["directory_service"])
        except SystemExit:
            return
        except Exception as e:
            self.exceptions.append(f"Creation of user failed for calm with the error: {e}")
            return

    def execute(self, **kwargs):
        try:
            # Get the number of available CPU cores
            num_cores = multiprocessing.cpu_count()

            # Set the value of max_workers based on the number of CPU cores
            max_workers = min(num_cores + 4, 5)

            # existing users
            client = get_api_client()
            user_names = set()

            for offset in [0, 200]:
                params = {"length": 200, "offset": offset}

                res, err = client.user.list(params=params)

                if err:
                    raise Exception("Cannot fetch NCM Users")

                users_json = res.json()
                user_entities = users_json["entities"]
                user_names = user_names.union({user.get("status", {}).get("name") for user in user_entities})

            users_list = []
            for user in self.users:
                if user in user_names:
                    logger.error(f"User already exists {user}")
                    continue
                users_list.append({"name": user, "directory_service": self.data["directory_services"]["ad_name"]})
            # Create users in batches of 5
            user_chunks = [
                users_list[i:i + 5]
                for i in range(0, len(users_list), 5)
            ] if users_list else []

            for users in user_chunks:
                try:
                    # Create maximum of 5 worker threads at a time
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        for result in executor.map(self.create_user_template, users):
                            logger.info(result)
                except Exception as e:
                    self.exceptions.append(e)
        except Exception as e:
            self.exceptions.append(e)
        except SystemExit as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        try:
            self.results["Create_Ncm_users"] = {}
            client = get_api_client()

            # Get 400 users potentially. 200 at a time (limit is 250)
            user_names = set()
            for offset in [0, 200]:
                params = {"length": 200, "offset": offset}

                res, err = client.user.list(params=params)

                if err:
                    raise Exception("Cannot fetch NCM Users")

                users_json = res.json()
                user_entities = users_json["entities"]
                user_names = user_names.union({user.get("status", {}).get("name") for user in user_entities})

            if not user_names:
                logger.error("No Users found!")

            for user in self.data.get("ncm_users"):
                if user in user_names:
                    self.results["Create_Ncm_users"][user] = "PASS"
                else:
                    self.results["Create_Ncm_users"][user] = "FAIL"
        except SystemExit as e:
            self.exceptions.append(e)
