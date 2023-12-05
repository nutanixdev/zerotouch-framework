import multiprocessing
import threading
import concurrent.futures
from typing import Dict
from calm.dsl.api import get_api_client
from calm.dsl.cli import sync_cache
from calm.dsl.cli.projects import compile_project_dsl_class, create_project, delete_project
from framework.helpers.log_utils import get_logger
from .script import Script
from calm.dsl.store import Cache
from calm.dsl.constants import CACHE
from calm.dsl.builtins import Project, Provider, Ref

logger = get_logger(__name__)


class CreateNcmProject(Script):
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        super(CreateNcmProject, self).__init__(**kwargs)
        self.logger = self.logger or logger

    @staticmethod
    def set_current_thread_name(project: str):
        current_thread = threading.current_thread()

        if current_thread != threading.main_thread():
            current_thread.name = f"Thread-CreateCalmProject-{project}"

    def create_project_template(self, project: Dict):
        self.set_current_thread_name(project.get("name"))

        try:
            class ProjectTemplate(Project):
                """DSL Project template"""
                providers = [
                    Provider.Ntnx(
                        account=Ref.Account(project.get("account_name")),
                        subnets=[Ref.Subnet(name=subnet, cluster=cluster_name)
                                 for cluster_name, subnet_list in project.get("subnets", {}).items() for subnet in
                                 subnet_list],
                    )
                ]

                users = [Ref.User(name=user) for user in project.get("users", [])]

            user_project = ProjectTemplate
            project_payload = compile_project_dsl_class(user_project)
            project_data = create_project(
                project_payload, name=project.get("name"), description=project.get("description")
            )
            project_uuid = project_data["uuid"] if project_data else None

            logger.info("[Done]")
            return project_uuid
        except SystemExit:
            return
        except Exception as e:
            self.exceptions.append(f"failed for the project "
                                   f"{project.get('name')} with the error: {e}")
            return

    def execute(self, **kwargs):
        try:
            sync_cache()
            # Get the number of available CPU cores
            num_cores = multiprocessing.cpu_count()

            # Set the value of max_workers based on the number of CPU cores
            max_workers = min(num_cores + 4, 5)

            # Create projects in batches of 5
            project_chunks = [
                self.data["projects"][i:i + 5]
                for i in range(0, len(self.data["projects"]), 5)
            ] if self.data.get("projects") else []

            for projects in project_chunks:
                try:
                    # Create maximum of 5 worker threads at a time
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        for result in executor.map(self.create_project_template, projects):
                            logger.debug(result)
                except Exception as e:
                    self.exceptions.append(e)
                # sleep for 5 seconds after each batch

            # Update cache after creation
            Cache.sync_table(CACHE.ENTITY.PROJECT)
            # sync_cache()
            # delete_project([f"project-site01-cluster-0{i}" for i in range(1, 10)])
            # delete_project([f"project-site01-cluster-{i}" for i in range(10, 31)])
        except Exception as e:
            self.exceptions.append(e)
        except SystemExit as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        try:
            self.results["Create_Ncm_projects"] = {}
            client = get_api_client()

            # Get 400 projects potentially. 200 at a time (limit is 250)
            project_names = set()
            for offset in [0, 200]:
                params = {"length": 200, "offset": offset}

                res, err = client.project.list(params=params)

                if err:
                    raise Exception("Cannot fetch NCM projects")

                projects_json = res.json()
                project_entities = projects_json["entities"]
                project_names = project_names.union({project.get("status", {}).get("name")
                                                     for project in project_entities})

            if not project_names:
                logger.error("No projects found!")

            for project in self.data.get("projects"):
                if project.get("name") in project_names:
                    self.results["Create_Ncm_projects"][project["name"]] = "PASS"
                else:
                    self.results["Create_Ncm_projects"][project["name"]] = "FAIL"
        except SystemExit as e:
            self.exceptions.append(e)
