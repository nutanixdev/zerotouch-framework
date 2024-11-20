import os  # no_qa
from calm.dsl.builtins import *  # no_qa

# Secret Variables
CENTOS_KEY = read_local_file("centos_private_key")
Mongo_PASSWORD = read_local_file(
    "MONGO_PASSWORD"
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

# These variables will be injected into this dsl-file from the input configuration file.
# Do not un-comment the section
# These are different from launch/ run-time parameters
# You can use these variables directly in the dsl-code i.e ACCOUNT_NAME etc and ignore editor/ IDE errors on these
# variables
INJECTED_VARIABLES = {
    "ACCOUNT_NAME",
    "SUBNET_NAME",
    "CLUSTER_NAME",
    "PROJECT_NAME",
    "IMAGE_NAME",
    "CATEGORIES"
}


class MONGOService(Service):
    @action
    def PackageInstall(name="Package Install"):

        CalmTask.Exec.ssh(
            name="Install Mongo",
            filename=os.path.join(
                "scripts", "PackageInstallMongo.sh"
            ),
            cred=ref(CENTOS_CRED),
            target=ref(MONGOService),
        )


class MongoVMResources(AhvVmResources):

    memory = 2
    vCPUs = 1
    cores_per_vCPU = 1
    if IMAGE_NAME:
        disks = [
            AhvVmDisk.Disk.Scsi.cloneFromImageService(IMAGE_NAME, bootable=True)
        ]
    else:
        disks = [
            AhvVmDisk.Disk.Scsi.cloneFromVMDiskPackage(AHV_CENTOS_78, bootable=True)
        ]

    nics = [AhvVmNic.NormalNic.ingress(SUBNET_NAME, cluster=CLUSTER_NAME)]

    guest_customization = AhvVmGC.CloudInit(
        filename=os.path.join("specs", "basic_linux_vm_cloudinit.yaml")
    )


class MongoVm(AhvVm):

    name = "Mongo-VM"
    resources = MongoVMResources
    cluster = Ref.Cluster(CLUSTER_NAME, account_name=ACCOUNT_NAME)
    categories = {"AppTier": "DB"} | CATEGORIES


class AHVMongoSubstrate(Substrate):

    os_type = "Linux"
    provider_type = "AHV_VM"
    account = Ref.Account(ACCOUNT_NAME)
    provider_spec = MongoVm
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

    memory = 2
    vCPUs = 1
    cores_per_vCPU = 1
    if IMAGE_NAME:
        disks = [
            AhvVmDisk.Disk.Scsi.cloneFromImageService(IMAGE_NAME, bootable=True)
        ]
    else:
        disks = [
            AhvVmDisk.Disk.Scsi.cloneFromVMDiskPackage(AHV_CENTOS_78, bootable=True)
        ]

    nics = [AhvVmNic.NormalNic.ingress(SUBNET_NAME, cluster=CLUSTER_NAME)]

    guest_customization = AhvVmGC.CloudInit(
        filename=os.path.join("specs", "basic_linux_vm_cloudinit.yaml")
    )


class ApacheVm(AhvVm):

    name = "APACHE_PHP-VM-@@{calm_array_index}@@"
    resources = ApacheVmResources
    cluster = Ref.Cluster(CLUSTER_NAME, account_name=ACCOUNT_NAME)
    categories = {"AppTier": "APP"} | CATEGORIES


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

    memory = 2
    vCPUs = 1
    cores_per_vCPU = 1
    if IMAGE_NAME:
        disks = [
            AhvVmDisk.Disk.Scsi.cloneFromImageService(IMAGE_NAME, bootable=True)
        ]
    else:
        disks = [
            AhvVmDisk.Disk.Scsi.cloneFromVMDiskPackage(AHV_CENTOS_78, bootable=True)
        ]

    nics = [AhvVmNic.NormalNic.ingress(SUBNET_NAME, cluster=CLUSTER_NAME)]

    guest_customization = AhvVmGC.CloudInit(
        filename=os.path.join("specs", "basic_linux_vm_cloudinit.yaml")
    )


class HAPROXYVm(AhvVm):

    name = "HAPROXY-VM"
    resources = HAPROXYVmResources
    cluster = Ref.Cluster(CLUSTER_NAME, account_name=ACCOUNT_NAME)
    categories = {"AppTier": "WEB"} | CATEGORIES


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

    dependencies = [ref(MONGOService)]

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


class MONGOPackage(Package):

    services = [ref(MONGOService)]

    @action
    def __install__():

        MONGOService.PackageInstall(name="Package Install")


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


class AhvMongoDeployment(Deployment):

    min_replicas = "1"
    max_replicas = "1"
    default_replicas = "1"

    packages = [ref(MONGOPackage)]
    substrate = ref(AHVMongoSubstrate)


class HAPROXYPackage(Package):

    services = [ref(HAPROXYService)]

    @action
    def __install__():

        HAPROXYService.PackageInstall(name="Package Install")


class AhvApacheDeployment(Deployment):

    min_replicas = "1"
    max_replicas = "2"
    default_replicas = "1"

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
        AhvMongoDeployment,
        AhvApacheDeployment,
        AhvHAProxyDeployment,
    ]

    Mongo_PASSWORD = CalmVariable.Simple.Secret(
        Mongo_PASSWORD,
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


class LAMP(Blueprint):
    """* [Lamp](http://@@{HAPROXY.address}@@)"""

    services = [MONGOService, APACHEService, HAPROXYService]
    packages = [MONGOPackage, APACHEPackage, HAPROXYPackage, AHV_CENTOS_78]
    substrates = [AHVMongoSubstrate, AhvApacheSubstrate, AhvHAPROXYSubstrate]
    profiles = [Nutanix]
    credentials = [CENTOS_CRED]


class BpMetadata(Metadata):
    categories = {"AppFamily": "DevOps"}
    project = Ref.Project(PROJECT_NAME)


def main():
    print(LAMP.json_dumps(pprint=True))


if __name__ == "__main__":
    main()
