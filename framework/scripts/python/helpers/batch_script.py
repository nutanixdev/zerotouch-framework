import concurrent.futures
import multiprocessing
from helpers.log_utils import get_logger
from scripts.python.script import Script

logger = get_logger(__name__)


class BatchScript(Script):
    """
    We can group scripts together and execute them in serial or parallel
    """

    def __init__(self, parallel: bool = False, **kwargs):
        """
        Constructor for BatchScript.
        Args:
           kwargs(dict):
            parallel(bool, optional): Whether to run the sub-steps in parallel,
              default value is False
        """
        self.script_list = []
        self._parallel = parallel
        self.num_total_scripts = 0
        self.num_passed_scripts = 0
        self.pass_rate = 0.0
        super(BatchScript, self).__init__()

    def add(self, script):
        """
        Add one script

        Args:
          script(Operation): The script object to be added to the group.

        Returns:
          None
        """
        if not script:
            logger.error("Script is none, returning.")
            return
        self.script_list.append(script)

    def add_all(self, script_list):
        """
        Add a list of scripts
        Args:
          script_list(list): A list of scripts to be added.

        Returns:
          None
        """
        if script_list:
            for op in script_list:
                self.add(op)

    def run(self):
        """
        Execute all the scripts in sequential or parallel

        Returns:
          None
        """

        if self._parallel:
            self._parallel_execute()
        else:
            self._sequential_execute()

    def _sequential_execute(self):
        """
        Execute all the steps in sequential.

        Returns
          None
        """
        for script in self.script_list:
            try:
                script.run()
            except Exception as e:
                logger.error(e)

    def _parallel_execute(self):
        """
        Execute all the scripts in parallel.

        Returns:
          None
        """
        # Get the number of available CPU cores
        num_cores = multiprocessing.cpu_count()

        # Set the value of max_workers based on the number of CPU cores
        max_workers = num_cores
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(lambda script: script.run(), self.script_list):
                try:
                    logger.debug(result)
                except Exception as e:
                    logger.error(e)

    def execute(self):
        pass

    def verify(self, **kwargs):
        pass
