import threading
import multiprocessing
import concurrent.futures
from abc import abstractmethod
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CvmScript(Script):
    def __init__(self, data: Dict, parallel: bool = True, **kwargs):
        self.data = data
        self.cvms = self.data.get("cvms", {})
        self.parallel = parallel
        super(CvmScript, self).__init__(**kwargs)
        self.results["cvms"] = {}
        # Set the value of max_workers based on the number of CPU cores
        self.max_workers = multiprocessing.cpu_count() + 4

    def execute(self, **kwargs):
        if self.parallel:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    executor.map(self.execute_single_cvm, self.cvms.keys(), self.cvms.values())
            except Exception as e:
                self.exceptions.append(e)
        else:
            try:
                for cvm_ip, cvm_details in self.cvms.items():
                    self.execute_single_cvm(cvm_ip, cvm_details)
            except Exception as e:
                self.exceptions.append(e)

    def verify(self, **kwargs):
        if self.parallel:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                executor.map(self.verify_single_cvm, self.cvms.keys(), self.cvms.values())
        else:
            try:
                for cvm_ip, cvm_details in self.cvms.items():
                    self.verify_single_cvm(cvm_ip, cvm_details)
            except Exception as e:
                self.exceptions.append(e)

    @abstractmethod
    def execute_single_cvm(self, cvm_ip: str, cvm_details: Dict):
        pass

    @abstractmethod
    def verify_single_cvm(self, cvm_ip: str, cvm_details: Dict):
        pass

    def set_current_thread_name(self, cvm_ip: str):
        current_thread = threading.current_thread()

        if current_thread != threading.main_thread():
            current_thread.name = f"Thread-{type(self).__name__}-{cvm_ip}"
