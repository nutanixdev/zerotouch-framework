from copy import deepcopy
from typing import Optional, Dict
from framework.scripts.python.pe.create.create_pe_subnets import CreateSubnetPe
from framework.scripts.python.pe.create.add_ad_server_pe import AddAdServerPe
from framework.scripts.python.pe.create.create_container_pe import CreateContainerPe
# from framework.scripts.python.pc.create.create_pc_subnets import CreateSubnetsPc
from framework.scripts.python.pe.create.create_rolemapping_pe import CreateRoleMappingPe
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.pe.other_ops.accept_eula import AcceptEulaPe
from framework.scripts.python.pe.other_ops.change_system_password import ChangeDefaultAdminPasswordPe
from framework.scripts.python.pe.other_ops.open_replication_ports_clusters import OpenRepPort
from framework.scripts.python.pe.other_ops.register_pe_to_pc import RegisterToPc
from framework.scripts.python.pe.other_ops.update_dsip_pe import UpdateDsip
from framework.scripts.python.pe.other_ops.update_pulse import UpdatePulsePe
from framework.scripts.python.script import Script
from framework.scripts.python.pe.create.add_ntp_server_pe import AddNtpServersPe
from framework.scripts.python.pe.create.add_name_server_pe import AddNameServersPe
from framework.scripts.python.pe.update.ha_reservation import HaReservation
from framework.scripts.python.pe.update.rebuild_capacity_reservation import RebuildCapacityReservation
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import create_pe_objects

logger = get_logger(__name__)


class ClusterConfig(Script):
    """
    Configure Cluster with below configs
    """

    def __init__(self, data: Dict, global_data: Dict = None, results_key: str = "", log_file: Optional[str] = None,
                 **kwargs):
        self.data = data
        self.global_data = deepcopy(global_data) if global_data else {}
        self.results_key = results_key
        self.log_file = log_file
        super(ClusterConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        create_pe_objects(self.data, global_data=self.global_data)
        if not self.data.get("vaults"):
            self.data["vaults"] = self.global_data.get("vaults")
        if not self.data.get("vault_to_use"):
            self.data["vault_to_use"] = self.global_data.get("vault_to_use")

        cluster_batch_scripts = BatchScript(results_key=self.results_key)

        # Initial cluster config in all clusters
        cluster_batch_scripts.add(
            ChangeDefaultAdminPasswordPe(self.data, log_file=self.log_file)
        )

        # Add Auth, AcceptEulaPe, UpdatePulsePe, Register PE to PC, Create containers, Add NTP, Add Name servers,
        # CreateSubnetPe -> needs ChangeDefaultAdminPasswordPe
        # Don't know if we can execute OpenRepPort, before or with ChangeDefaultAdminPasswordPe, so keeping it here
        main_cluster_batch_scripts = BatchScript(parallel=True)
        main_cluster_batch_scripts.add_all([
            AcceptEulaPe(self.data, log_file=self.log_file),
            UpdatePulsePe(self.data, log_file=self.log_file),
            AddAdServerPe(self.data, log_file=self.log_file),
            OpenRepPort(self.data, log_file=self.log_file),
            CreateContainerPe(self.data, log_file=self.log_file),
            AddNtpServersPe(self.data, log_file=self.log_file),
            AddNameServersPe(self.data, log_file=self.log_file),
            CreateSubnetPe(self.data, log_file=self.log_file),
            HaReservation(self.data, log_file=self.log_file),
            RebuildCapacityReservation(self.data, log_file=self.log_file)
        ])
        if not self.data.get("skip_pc_registration") and self.data.get("pc_ip") and self.data.get("pc_credential"):
            main_cluster_batch_scripts.add(RegisterToPc(self.data, log_file=self.log_file))
        cluster_batch_scripts.add(main_cluster_batch_scripts)

        # Update DSIP -> needs ChangeDefaultAdminPasswordPe, fails if we update DSIP with Auth
        # Add Role-mappings -> needs AddAdServer
        primary_cluster_batch_scripts = BatchScript(parallel=True)
        primary_cluster_batch_scripts.add_all([
            UpdateDsip(self.data, log_file=self.log_file),
            CreateRoleMappingPe(self.data, log_file=self.log_file)
        ])
        cluster_batch_scripts.add(primary_cluster_batch_scripts)

        self.results.update(cluster_batch_scripts.run())
        self.data["json_output"] = self.results

    def verify(self):
        pass
