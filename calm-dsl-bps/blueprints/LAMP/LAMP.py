import os  # no_qa
from pathlib import Path
from calm.dsl.builtins import *  # no_qa
from helpers.general_utils import get_json_file_contents

# Secret Variables
CENTOS_KEY = read_local_file("centos_private_key")
MYSQL_PASSWORD = read_local_file(
    "MYSQL_PASSWORD"
)

# Credentials
CENTOS_CRED = basic_cred(
    "centos",
    CENTOS_KEY,
    name="CENTOS",
    type="KEY",
    default=True,
    editables={"username": True, "secret": True},
)


# Downloadable images for AHV
AHV_CENTOS_78 = vm_disk_package(
    name="AHV_CENTOS_78", config_file="specs/ahv_centos.yaml"
)

# Subnet, Cluster reference
# Find path to the project root
# we are in root/blueprints/LAMP/
project_root = Path(__file__).parent.parent.parent.parent

# todo Convert this to Run time variables and pass it from script
spec = get_json_file_contents(f"{project_root}/config/create-vm-workloads.json")
ACCOUNT_NAME = spec["account_name"]
bp_spec = spec["bp_list"]

for bp in bp_spec:
    if bp["name"] == "LAMP-dsl":
        subnet_name = bp["subnet"]
        cluster_name = bp["cluster"]
    else:
        raise Exception("Cluster and Subnet not specified")


class MYSQLService(Service):
    @action
    def PackageInstall(name="Package Install"):

        CalmTask.Exec.ssh(
            name="Install MySQL",
            filename=os.path.join(
                "scripts", "PackageInstallMySQL.sh"
            ),
            cred=ref(CENTOS_CRED),
            target=ref(MYSQLService),
        )


class MYSQLVMResources(AhvVmResources):

    memory = 4
    vCPUs = 2
    cores_per_vCPU = 2
    disks = [
        AhvVmDisk.Disk.Scsi.cloneFromVMDiskPackage(AHV_CENTOS_78, bootable=True)
    ]

    nics = [AhvVmNic.NormalNic.ingress(subnet_name, cluster=cluster_name)]

    guest_customization = AhvVmGC.CloudInit(
        filename=os.path.join("specs", "basic_linux_vm_cloudinit.yaml")
    )


class MYSQLVm(AhvVm):

    name = "MYSQL-VM"
    resources = MYSQLVMResources
    cluster = Ref.Cluster(cluster_name)


class AHVMysqlSubstrate(Substrate):

    os_type = "Linux"
    provider_type = "AHV_VM"
    account = Ref.Account(ACCOUNT_NAME)
    provider_spec = MYSQLVm
    provider_spec_editables = read_spec(
        os.path.join("specs", "basic_linux_vm_editables.yaml")
    )
    readiness_probe = readiness_probe(
        connection_type="SSH",
        disabled=False,
        retries="5",
        connection_port=22,
        address="@@{platform.status.resources.nic_list[0].ip_endpoint_list[0].ip}@@",
        delay_secs="300",
        credential=ref(CENTOS_CRED)
    )


class ApacheVmResources(AhvVmResources):

    memory = 4
    vCPUs = 2
    cores_per_vCPU = 2
    disks = [AhvVmDisk.Disk.Scsi.cloneFromVMDiskPackage(AHV_CENTOS_78, bootable=True)]

    nics = [AhvVmNic.NormalNic.ingress(subnet_name, cluster=cluster_name)]

    guest_customization = AhvVmGC.CloudInit(
        filename=os.path.join("specs", "basic_linux_vm_cloudinit.yaml")
    )


class ApacheVm(AhvVm):

    name = "APACHE_PHP-VM-@@{calm_array_index}@@"
    resources = ApacheVmResources
    cluster = Ref.Cluster(cluster_name)


class AhvApacheSubstrate(Substrate):

    os_type = "Linux"
    provider_type = "AHV_VM"
    provider_spec = ApacheVm
    account = Ref.Account(ACCOUNT_NAME)
    provider_spec_editables = read_spec(
        os.path.join("specs", "basic_linux_vm_editables.yaml")
    )
    readiness_probe = readiness_probe(
        connection_type="SSH",
        disabled=False,
        retries="5",
        connection_port=22,
        address="@@{platform.status.resources.nic_list[0].ip_endpoint_list[0].ip}@@",
        delay_secs="300",
        credential=ref(CENTOS_CRED),
        editables_list=[],
    )


class HAPROXYVmResources(AhvVmResources):

    memory = 4
    vCPUs = 2
    cores_per_vCPU = 1
    disks = [AhvVmDisk.Disk.Scsi.cloneFromVMDiskPackage(AHV_CENTOS_78, bootable=True)]

    nics = [AhvVmNic.NormalNic.ingress(subnet_name, cluster=cluster_name)]

    guest_customization = AhvVmGC.CloudInit(
        filename=os.path.join("specs", "basic_linux_vm_cloudinit.yaml")
    )


class HAPROXYVm(AhvVm):

    name = "HAPROXY-VM"
    resources = HAPROXYVmResources
    cluster = Ref.Cluster(cluster_name)


class AhvHAPROXYSubstrate(Substrate):

    os_type = "Linux"
    provider_type = "AHV_VM"
    provider_spec = HAPROXYVm
    account = Ref.Account(ACCOUNT_NAME)
    provider_spec_editables = read_spec(
        os.path.join("specs", "basic_linux_vm_editables.yaml")
    )
    readiness_probe = readiness_probe(
        connection_type="SSH",
        disabled=False,
        retries="5",
        connection_port=22,
        address="@@{platform.status.resources.nic_list[0].ip_endpoint_list[0].ip}@@",
        delay_secs="300",
        credential=ref(CENTOS_CRED),
        editables_list=[],
    )


class APACHEService(Service):

    dependencies = [ref(MYSQLService)]

    @action
    def PackageInstall(name="Package Install"):

        CalmTask.Exec.ssh(
            name="Install Apache",
            filename=os.path.join(
                "scripts",
                "PackageInstallApache.sh",
            ),
            cred=ref(CENTOS_CRED),
            target=ref(APACHEService),
        )


class MYSQLPackage(Package):

    services = [ref(MYSQLService)]

    @action
    def __install__():

        MYSQLService.PackageInstall(name="Package Install")


class HAPROXYService(Service):

    dependencies = [ref(APACHEService)]

    @action
    def PackageInstall(name="Package Install"):

        CalmTask.Exec.ssh(
            name="Install HAProxy",
            filename=os.path.join(
                "scripts",
                "PackageInstallHAProxy.sh",
            ),
            cred=ref(CENTOS_CRED),
            target=ref(HAPROXYService),
        )


class APACHEPackage(Package):

    services = [ref(APACHEService)]

    @action
    def __install__():

        APACHEService.PackageInstall(name="Package Install")


class AhvMYSQLDeployment(Deployment):

    min_replicas = "1"
    max_replicas = "1"
    default_replicas = "1"

    packages = [ref(MYSQLPackage)]
    substrate = ref(AHVMysqlSubstrate)


class HAPROXYPackage(Package):

    services = [ref(HAPROXYService)]

    @action
    def __install__():

        HAPROXYService.PackageInstall(name="Package Install")


class AhvApacheDeployment(Deployment):

    min_replicas = "2"
    max_replicas = "4"
    default_replicas = "2"

    packages = [ref(APACHEPackage)]
    substrate = ref(AhvApacheSubstrate)
    editables = {
        "min_replicas": False,
        "default_replicas": False,
        "max_replicas": False,
    }


class AhvHAProxyDeployment(Deployment):

    min_replicas = "1"
    max_replicas = "1"
    default_replicas = "1"

    packages = [ref(HAPROXYPackage)]
    substrate = ref(AhvHAPROXYSubstrate)


class Nutanix(Profile):

    deployments = [
        AhvMYSQLDeployment,
        AhvApacheDeployment,
        AhvHAProxyDeployment,
    ]

    MYSQL_PASSWORD = CalmVariable.Simple.Secret(
        MYSQL_PASSWORD,
        label="",
        is_mandatory=False,
        is_hidden=False,
        runtime=False,
        description="",
    )

    @action
    def ScaleOut():
        """This action will scale out App Server slaves by given scale out count."""

        COUNT = CalmVariable.Simple(
            "1",
            label="",
            is_mandatory=False,
            is_hidden=False,
            runtime=True,
            description="",
        )
        CalmTask.Scaling.scale_out(
            "@@{COUNT}@@", name="Scale Out App", target=ref(AhvApacheDeployment)
        )
        CalmTask.Exec.ssh(
            name="Configure haproxy",
            filename=os.path.join(
                "scripts", "ScaleOutApacheConfigurehaproxy.sh"
            ),
            cred=ref(CENTOS_CRED),
            target=ref(HAPROXYService),
        )

    @action
    def ScaleIn():
        """This action will scale in App Server slaves by given scale in count."""

        COUNT = CalmVariable.Simple(
            "1",
            label="",
            is_mandatory=False,
            is_hidden=False,
            runtime=True,
            description="",
        )
        CalmTask.Scaling.scale_in(
            "@@{COUNT}@@", name="Scale In App", target=ref(AhvApacheDeployment)
        )
        CalmTask.Exec.ssh(
            name="Configure haproxy",
            filename=os.path.join(
                "scripts", "ScaleInApacheConfigurehaproxy.sh"
            ),
            cred=ref(CENTOS_CRED),
            target=ref(HAPROXYService),
        )

    @action
    def DBBackup():
        """This action will take mysql backup."""

        BACKUP_FILE_PATH = CalmVariable.Simple(
            "~/db_backup",
            label="",
            is_mandatory=False,
            is_hidden=False,
            runtime=True,
            description="",
        )
        CalmTask.Exec.ssh(
            name="Do DB Backup",
            filename=os.path.join(
                "scripts", "MySqlDbBackup.sh"
            ),
            target=ref(MYSQLService),
        )

    @action
    def DBRestore():
        """This action will restore mysql db from specified file."""

        RESTORE_FILE_PATH = CalmVariable.Simple(
            "~/db_backup/db_dump.sql.gz",
            label="",
            is_mandatory=False,
            is_hidden=False,
            runtime=True,
            description="",
        )
        CalmTask.Exec.ssh(
            name="Do DB Restore",
            filename=os.path.join(
                "scripts", "MySqlDbRestore.sh"
            ),
            target=ref(MYSQLService),
        )


class LAMP(Blueprint):
    """* [Lamp](http://@@{HAPROXY.address}@@)"""

    services = [MYSQLService, APACHEService, HAPROXYService]
    packages = [MYSQLPackage, APACHEPackage, HAPROXYPackage, AHV_CENTOS_78]
    substrates = [AHVMysqlSubstrate, AhvApacheSubstrate, AhvHAPROXYSubstrate]
    profiles = [Nutanix]
    credentials = [CENTOS_CRED]


class BpMetadata(Metadata):

    categories = {"AppFamily": "DevOps"}


def main():
    print(LAMP.json_dumps(pprint=True))


if __name__ == "__main__":
    main()
