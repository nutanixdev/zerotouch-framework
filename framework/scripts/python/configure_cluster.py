import time
from copy import deepcopy
from typing import Optional, Dict
from .add_ad_server_pe import AddAdServerPe
from .create_container_pe import CreateContainerPe
from .create_pc_subnets import CreateSubnetsPc
from .create_rolemapping_pe import CreateRoleMappingPe
from .helpers.batch_script import BatchScript
from .initial_cluster_config import InitialClusterConfig
from .register_pe_to_pc import RegisterToPc
from .update_dsip_pe import UpdateDsip
from .script import Script
from .add_ntp_server_pe import AddNtpServersPe
from .add_name_server_pe import AddNameServersPe
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class ClusterConfig(Script):
    """
    Configure Cluster with below configs
    """

    def __init__(self, data: Dict, results_key: str = "", log_file: Optional[str] = None, **kwargs):
        self.data = data
        self.results_key = results_key
        self.log_file = log_file
        super(ClusterConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        data = deepcopy(self.data)
        cluster_batch_scripts = BatchScript(results_key=self.results_key)

        # Initial cluster config in all clusters
        cluster_batch_scripts.add(InitialClusterConfig(data, log_file=self.log_file))

        # Add Auth -> needs InitialClusterConfig
        cluster_batch_scripts.add(AddAdServerPe(data, log_file=self.log_file))
        time.sleep(10)

        # Register PE to PC -> needs InitialClusterConfig
        # Create containers in PE -> needs InitialClusterConfig
        # Update DSIP -> needs InitialClusterConfig, fails if we update DSIP with Auth
        # Add Role-mappings -> needs AddAdServer
        # Add NTP servers -> InitialClusterConfig
        # Add Name servers -> InitialClusterConfig
        primary_cluster_batch_scripts = BatchScript(parallel=True)
        primary_cluster_batch_scripts.add_all([
            RegisterToPc(data, log_file=self.log_file),
            CreateContainerPe(data, log_file=self.log_file),
            UpdateDsip(data, log_file=self.log_file),
            CreateRoleMappingPe(data, log_file=self.log_file),
            AddNtpServersPe(data, log_file=self.log_file),
            AddNameServersPe(data, log_file=self.log_file)
        ])
        cluster_batch_scripts.add(primary_cluster_batch_scripts)

        # Create Subnets in PC -> needs RegisterToPc
        subnet_batch_script = BatchScript(parallel=True)
        subnet_batch_script.add(CreateSubnetsPc(data, log_file=self.log_file))
        cluster_batch_scripts.add(subnet_batch_script)
        self.results.update(cluster_batch_scripts.run())

    def verify(self):
        pass
