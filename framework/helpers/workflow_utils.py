from typing import Type, List, Callable
from framework.scripts.python.script import Script
from .general_utils import run_script
from .log_utils import get_logger

logger = get_logger(__name__)

class Workflow:
    """
    A class to represent a workflow.

    Attributes:
    ----------
    data : dict
        A dictionary containing workflow data.

    Methods:
    -------
    run_scripts(scripts: List[Type[Script]]):
        Runs the provided scripts.

    run_functions(functions: List[Callable]):
        Runs the provided functions.
    """

    def __init__(self, **data):
        """
        Constructs all the necessary attributes for the Workflow object.

        Parameters:
        ----------
        data : dict
            A dictionary containing workflow data.
        """
        self.data = data

    def run_scripts(self, scripts: List[Type[Script]]):
        """
        Runs the provided scripts.

        Parameters:
        ----------
        scripts : List[Type[Script]]
            A list of script classes to be run.
        """
        logger.info(f"Running the {type(self).__name__}...")

        # run the scripts
        run_script(scripts, self.data)

    def run_functions(self, functions: List[Callable]):
        """
        Runs the provided functions.

        Parameters:
        ----------
        functions : List[Callable]
            A list of functions to be run.
        """
        for func in functions:
            logger.info(f"Calling the action '{func.__name__}'...")
            func(self.data)