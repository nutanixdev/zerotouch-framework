import concurrent.futures
import multiprocessing
from typing import Dict
from framework.helpers.log_utils import get_logger
from ..script import Script

logger = get_logger(__name__)


class BatchScript(Script):
    """
    We can group scripts together and execute them in serial or parallel
    """

    def __init__(self, results_key: str = "", parallel: bool = False, **kwargs):
        """
        Constructor for BatchScript.
        Args:
           kwargs(dict):
            parallel(bool, optional): Whether to run the sub-steps in parallel,
              default value is False
        """
        self.script_list = []
        self._results = {}
        # Results key is used to consolidate the results coming from different scripts, batch scripts. If results_key
        # is passed the return value of the run function would be {"results_key": self._results}, which would be
        # consolidated into results, by results setter in parent BatchScript.
        self.results_key = results_key
        # Set max_workers that can run in parallel
        self.max_workers = kwargs.get("max_workers") or multiprocessing.cpu_count() + 4
        # If we can run scripts in parallel
        self._parallel = parallel
        super(BatchScript, self).__init__(**kwargs)
        self.logger = self.logger or logger

    @property
    def results(self):
        return self._results

    def consolidate_results(self, new_item: Dict, results: Dict = None):
        if not results:
            results = self._results
        for key, value in new_item.items():
            if key not in results:
                results[key] = value
                continue
            if isinstance(value, dict):
                results[key] = self.consolidate_results(results=results[key], new_item=value)
            else:
                # If the key is already there, replace the values
                results[key] = value

        return results

    @results.setter
    def results(self, new_item):
        if not new_item:
            return
        if not isinstance(new_item, dict):
            # Append all the non-dict return values
            if "results" not in self._results:
                self.results["results"] = []
            self._results["results"].append(new_item)
        else:
            # Consolidate all the dict return values
            self._results = self.consolidate_results(new_item)

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

        return {self.results_key: self.results} if self.results_key else self.results

    def _sequential_execute(self):
        """
        Execute all the steps in sequential.

        Returns
          None
        """
        for script in self.script_list:
            try:
                result = script.run()
                self.results = result
            except Exception as e:
                logger.error(e)

    def _parallel_execute(self):
        """
        Execute all the scripts in parallel.

        Returns:
          None
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for result in executor.map(lambda script: script.run(), self.script_list):
                try:
                    self.results = result
                except Exception as e:
                    logger.error(e)

    def execute(self):
        pass

    def verify(self, **kwargs):
        pass
