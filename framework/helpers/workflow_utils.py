from typing import Type, List, Callable
from framework.scripts.python.script import Script
from .general_utils import run_script
from .log_utils import get_logger

logger = get_logger(__name__)


class Workflow:
    def __init__(self, **data):
        self.data = data

    def run_scripts(self, scripts: List[Type[Script]]):
        logger.info(f"Running the {type(self).__name__}...")

        # run the scripts
        run_script(scripts, self.data)

    def run_functions(self, functions: List[Callable]):
        for func in functions:
            logger.info(f"Calling the action '{func.__name__}'...")
            func(self.data)
