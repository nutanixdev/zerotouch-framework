custom_helpers_registry = {
    "fc_v1_cluster": {
        "helper_class": "FcClusterHelper",
        "helper_module": "ztf.helpers.fc_cluster",
    },
    "fc_create_cluster": {
        "helper_class": "FcCreateClusterHelper",
        "helper_module": "ztf.helpers.fc_create_cluster",
    },
    "fc_v1_imaging": {
        "helper_class": "FcImagingHelper",
        "helper_module": "ztf.helpers.fc_imaging",
    },
    "foundation_central_service": {
        "helper_class": "FcImagingHelper",
        "helper_module": "ztf.helpers.fc_imaging",
    },
    "generate_fc_api_key": {
        "helper_class": "GenerateFcApiKeyHelper",
        "helper_module": "ztf.helpers.generate_fc_api_key",
    },
    "update_cvm_foundation": {
        "helper_class": "UpdateCvmFoundationHelper",
        "helper_module": "ztf.helpers.update_cvm_foundation",
    },
    "fc_v1_image_upload": {
        "helper_class": "FcImageUploadHelper",
        "helper_module": "ztf.helpers.fc_v1_image_upload",
    },
    # PE-direct backported entities (no v4 PC API available; see
    # manual_entities.yml in ztf-internal-scripts for the v4-verification notes)
    "eula_pe": {
        "helper_class": "EulaPeHelper",
        "helper_module": "ztf.helpers.eula_pe",
    },
    "ad_server_pe": {
        "helper_class": "AdServerPeHelper",
        "helper_module": "ztf.helpers.ad_server_pe",
    },
    "role_mapping_pe": {
        "helper_class": "RoleMappingPeHelper",
        "helper_module": "ztf.helpers.role_mapping_pe",
    },
    "open_replication_ports": {
        "helper_class": "OpenReplicationPortsHelper",
        "helper_module": "ztf.helpers.open_replication_ports",
    },
    "ha_reservation": {
        "helper_class": "HaReservationHelper",
        "helper_module": "ztf.helpers.ha_reservation",
    },
}
