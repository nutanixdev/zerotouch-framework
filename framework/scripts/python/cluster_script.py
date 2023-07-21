import threading
import multiprocessing
import concurrent.futures
from abc import abstractmethod
from helpers.log_utils import get_logger
from scripts.python.script import Script

logger = get_logger(__name__)


class ClusterScript(Script):
    def __init__(self, data: dict, parallel: bool = True, **kwargs):
        self.data = data
        # pass the Cluster Objects
        # create_pe_pc helper function can be used
        self.pe_clusters = self.data.get("clusters", {})
        self.parallel = parallel
        super(ClusterScript, self).__init__(**kwargs)
        self.results["clusters"] = {}

    def execute(self, **kwargs):
        if self.parallel:
            # Get the number of available CPU cores
            num_cores = multiprocessing.cpu_count()

            # Set the value of max_workers based on the number of CPU cores
            max_workers = num_cores + 4

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    executor.map(self.execute_single_cluster, self.pe_clusters.keys(), self.pe_clusters.values())
            except Exception as e:
                self.exceptions.append(e)
        else:
            try:
                for cluster_ip, cluster_details in self.pe_clusters.items():
                    self.execute_single_cluster(cluster_ip, cluster_details)
            except Exception as e:
                self.exceptions.append(e)

    @abstractmethod
    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        pass

    def verify(self, **kwargs):
        pass

    def set_current_thread_name(self, cluster_ip: str):
        current_thread = threading.current_thread()

        if current_thread != threading.main_thread():
            current_thread.name = f"Thread-{type(self).__name__}-{cluster_ip}"
