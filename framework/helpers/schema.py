from .general_utils import validate_ip, contains_whitespace, validate_domain, validate_ip_list, validate_subnet

"""
We are using a popular Python library "cerberus" to define the json/ yml schema
https://docs.python-cerberus.org/validation-rules.html
"""

# todo add dependencies to schema
GLOBAL_NETWORK_SCHEMA = {
    'required': True,
    'type': 'dict',
    'schema': {
        'ntp_servers': {
            'type': 'list',
            'required': False
        },
        'dns_servers': {
            'type': 'list',
            'required': False
        }
    }
}

USERNAME_PASSWORD_SCHEMA = {
    'required': True,
    'type': 'string',
    'validator': contains_whitespace
}

IMAGING_NETWORK = {
    'type': 'dict',
    'required': False,
    'schema': {
        'mgmt_static_ips': {
            'required': True,
            'type': 'list',
            'empty': True,
            'schema': {
                'type': 'string',
                'validator': validate_ip
            }
        },
        'mgmt_netmask': {
            'required': True,
            'type': 'string',
            'empty': True,
            'validator': validate_ip
        },
        'mgmt_gateway': {
            'required': True,
            'type': 'string',
            'empty': True,
            'validator': validate_ip
        },
        'ipmi_netmask': {
            'required': True,
            'type': 'string',
            'empty': True,
            'validator': validate_ip
        },
        'ipmi_gateway': {
            'required': True,
            'empty': True,
            'type': 'string',
            'validator': validate_ip
        },
        'ipmi_static_ips': {
            'required': True,
            'type': 'list',
            'empty': True,
            'schema': {
                'type': 'string',
                'validator': validate_ip
            }
        }
    }
}

IMAGING_SCHEMA = {
    'pod': {
        'type': 'dict',
        'required': True,
        'schema': {
            'pod_name': {
                'type': 'string',
                'required': True
            },
            'pod_blocks': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'pod_block_name': {
                            'type': 'string',
                            'required': True
                        },
                        'pc_ip': {
                            'type': 'string',
                            'required': True,
                            'validator': validate_ip
                        },
                        'pc_username': USERNAME_PASSWORD_SCHEMA,
                        'pc_password': USERNAME_PASSWORD_SCHEMA,
                        'edge-sites': {
                            'type': 'list',
                            'required': True,
                            'schema': {
                                'type': 'dict',
                                'schema': {
                                    'site_name': {
                                        'required': True,
                                        'type': 'string'
                                    },
                                    'node_block_serials': {
                                        'required': False,
                                        'type': 'list',
                                        'schema': {
                                            'type': 'string',
                                            'validator': contains_whitespace
                                        }
                                    },
                                    'use_existing_network_settings': {
                                        'required': True,
                                        'type': 'boolean'
                                    },
                                    're-image': {
                                        'required': True,
                                        'type': 'boolean'
                                    },
                                    'imaging_parameters': {
                                        'type': 'dict',
                                        'required': False,
                                        'schema': {
                                            'aos_version': {
                                                'required': True,
                                                'type': ['float', 'string']
                                            },
                                            'hypervisor_type': {
                                                'required': True,
                                                'type': 'string',
                                                'allowed': ['kvm', 'esx', 'hyperv']
                                            },
                                            'hypervisor_version': {
                                                'required': True,
                                                'type': ['float', 'string']
                                            }
                                        }
                                    },
                                    'network': IMAGING_NETWORK,
                                    'clusters': {
                                        'type': 'list',
                                        'required': True,
                                        'schema': {
                                            'type': 'dict',
                                            'schema': {
                                                'cluster_name': {
                                                    'type': 'string',
                                                    'required': True,
                                                },
                                                'cluster_size': {
                                                    'type': 'integer',
                                                    'required': True,
                                                },
                                                'cluster_vip': {
                                                    'type': 'string',
                                                    'required': True,
                                                    'validator': validate_ip
                                                },
                                                'cvm_ram': {
                                                    'type': 'integer',
                                                    'required': True,
                                                    'min': 12
                                                },
                                                'redundancy_factor': {
                                                    'type': 'integer',
                                                    'required': True,
                                                    'allowed': [2, 3]
                                                },
                                                'node_serials': {
                                                    'type': 'list',
                                                    'required': False,
                                                    'schema': {
                                                        'type': 'string',
                                                        'validator': contains_whitespace
                                                    }
                                                },
                                                'network': IMAGING_NETWORK,
                                                'use_existing_network_settings': {
                                                    'required': False,
                                                    'type': 'boolean'
                                                },
                                                're-image': {
                                                    'required': False,
                                                    'type': 'boolean'
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    'global_network': GLOBAL_NETWORK_SCHEMA
}

EULA_SCHEMA = {
    'type': 'dict',
    'schema': {
        'username': {
            'type': 'string',
            'required': True,
            'empty': False
        },
        'company_name': {
            'type': 'string',
            'required': True,
            'empty': False
        },
        'job_title': {
            'type': 'string',
            'required': True,
            'empty': False
        }
    }
}

PULSE_SCHEMA = {
    'type': 'boolean'
}

AD_SCHEMA = {
    'type': 'dict',
    'required': True,
    'schema': {
        'directory_type': {
            'type': 'string',
            'required': True,
            'allowed': ['ACTIVE_DIRECTORY'],
            'empty': False
        },
        'ad_name': {
            'type': 'string',
            'required': True,
            'empty': False
        },
        'ad_domain': {
            'type': 'string',
            'required': True,
            'empty': False,
            'validator': validate_domain
        },
        'ad_server_ip': {
            'type': 'string',
            'required': True,
            'empty': False,
            'validator': validate_ip
        },
        'service_account_username': {
            'type': 'string',
            'required': True,
            'empty': False,
            'validator': contains_whitespace
        },
        'service_account_password': {
            'type': 'string',
            'required': True,
            'empty': False,
            'validator': contains_whitespace
        },
        'role_mappings': {
            'type': 'list',
            'required': True,
            'schema': {
                'type': 'dict',
                'schema': {
                    'role_type': {
                        'required': True,
                        'type': 'string',
                        'allowed': ['ROLE_CLUSTER_ADMIN', 'ROLE_USER_ADMIN', 'ROLE_CLUSTER_VIEWER', 'ROLE_BACKUP_ADMIN']
                    },
                    'entity_type': {
                        'required': True,
                        'type': 'string',
                        'allowed': ['GROUP', 'OU', 'USER']
                    },
                    'values': {
                        'required': True,
                        'type': 'list'
                    }
                }
            }
        }
    }
}

PE_CONTAINERS_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {
                'type': 'string',
                'required': True
            },
            'advertisedCapacity_in_gb': {
                'type': 'integer',
                'required': False
            },
            'replication_factor': {
                'type': 'integer',
                'required': False
            },
            'compression_enabled': {
                'type': 'boolean',
                'required': False
            },
            'compression_delay_in_secs': {
                'type': 'integer',
                'required': False
            },
            'erasure_code': {
                'type': 'string',
                'required': False,
                'allowed': ['OFF', 'ON']
            },
            'on_disk_dedup': {
                'type': 'string',
                'required': False,
                'allowed': ['OFF', 'ON']
            },
            'nfsWhitelistAddress': {
                'type': 'list',
                'required': False
            }
        }
    }
}

PE_NETWORKS_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {
                'type': 'string',
            },
            'vlan_id': {
                'type': 'integer',
            },
            'network_ip': {
                'type': 'string',
                'validator': validate_ip
            },
            'network_prefix': {
                'type': 'integer'
            },
            'default_gateway_ip': {
                'type': 'string',
                'validator': validate_ip
            },
            'pool_list': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'range': {
                            'type': 'string'
                        }
                    }
                }
            },
            'dhcp_options': {
                'type': 'dict',
                'schema': {
                    'domain_name_server_list': {
                        'type': 'list',
                        'validator': validate_ip_list
                    },
                    'domain_search_list': {
                        'type': 'list',
                        'validator': validate_domain
                    },
                    'domain_name': {
                        'type': 'string',
                        'validator': validate_domain
                    }
                }
            }
        }
    }
}

REMOTE_AZS_SCHEMA = {
    'type': 'dict',
    'keyschema': {'type': 'string', 'validator': validate_ip},
    'valueschema': {
        'type': 'dict',
        'schema': {
            'username': {
                'type': 'string',
                'validator': contains_whitespace
            },
            'password': {
                'type': 'string',
                'validator': contains_whitespace
            }
        }
    }
}

PC_CATEGORIES_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'values': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                }
            }
        }
    }
}

RECOVERY_PLAN_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {
                'type': 'string'
            },
            'desc': {
                'type': 'string'
            },
            'primary_location': {
                'type': 'dict',
                'schema': {
                    'availability_zone': {
                        'type': 'string',
                        'validator': validate_ip
                    },
                }
            },
            'recovery_location': {
                'type': 'dict',
                'schema': {
                    'availability_zone': {
                        'type': 'string',
                        'validator': validate_ip
                    },
                }
            },
            'stages': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'vms': {
                            'type': 'list',
                            'schema': {
                                'type': 'dict',
                                'schema': {
                                    'name': {'type': 'string'},
                                    'enable_script_exec': {'type': 'boolean'},
                                    'delay': {'type': 'integer'}
                                }
                            }
                        },
                        'categories': {
                            'type': 'list',
                            'schema': {
                                'type': 'dict',
                                'schema': {
                                    'key': {'type': 'string'},
                                    'value': {'type': 'string'}
                                }
                            }
                        }
                    }
                }
            },
            'network_type': {
                'type': 'string',
                'allowed': ['NON_STRETCH', 'STRETCH']
            },
            'network_mappings': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'primary': {
                            'type': 'dict',
                            'schema': {
                                'test': {
                                    'type': 'dict',
                                    'schema': {
                                        'name': {'type': 'string'},
                                        'gateway_ip': {
                                            'type': 'string',
                                            'validator': validate_ip
                                        },
                                        'prefix': {'type': 'integer'}
                                    }
                                },
                                'prod': {
                                    'type': 'dict',
                                    'schema': {
                                        'name': {'type': 'string'},
                                        'gateway_ip': {
                                            'type': 'string',
                                            'validator': validate_ip
                                        },
                                        'prefix': {'type': 'integer'}
                                    }
                                },
                            }
                        },
                        'recovery': {
                            'type': 'dict',
                            'schema': {
                                'test': {
                                    'type': 'dict',
                                    'schema': {
                                        'name': {'type': 'string'},
                                        'gateway_ip': {
                                            'type': 'string',
                                            'validator': validate_ip
                                        },
                                        'prefix': {'type': 'integer'}
                                    }
                                },
                                'prod': {
                                    'type': 'dict',
                                    'schema': {
                                        'name': {'type': 'string'},
                                        'gateway_ip': {
                                            'type': 'string',
                                            'validator': validate_ip
                                        },
                                        'prefix': {'type': 'integer'}
                                    }
                                },
                            }
                        }
                    }
                }
            }
        }
    }
}

INBOUND_OUTBOUND_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'address': {
                'type': 'dict',
                'schema': {
                    'name': {'type': 'string'}
                }
            },
            'categories': {
                'type': 'dict',
                'keyschema': {'type': 'string'},
                'valueschema': {
                    'type': 'list'
                }
            },
            'protocol': {
                'type': 'dict',
                'schema': {
                    'service': {
                        'type': 'dict',
                        'schema': {
                            'name': {'type': 'string'}
                        }
                    }
                }
            }
        }
    }
}

RETENTION_POLICY_SCHEMA = {
    'type': 'dict',
    'schema': {
        'num_snapshots': {
            'type': 'integer'
        },
        'rollup_retention_policy': {
            'type': 'dict',
            'schema': {
                'snapshot_interval_type': {
                    'type': 'string',
                    'allowed': ['HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
                },
                'multiple': {'type': 'integer'}
            }
        }
    }
}

PROTECTION_RULES_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {
                'type': 'string'
            },
            'desc': {
                'type': 'string'
            },
            'protected_categories': {
                'type': 'dict',
                'keyschema': {'type': 'string'},
                'valueschema': {
                    'type': 'list'
                }
            },
            'schedules': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'source': {
                            'schema': {
                                'availability_zone': {
                                    'type': 'string',
                                    'validator': validate_ip
                                },
                                'clusters': {
                                    'type': 'list'
                                }
                            }
                        },
                        'destination': {
                            'type': 'dict',
                            'schema': {
                                'availability_zone': {
                                    'type': 'string',
                                    'validator': validate_ip
                                },
                                'cluster': {
                                    'type': 'string'
                                }
                            }
                        },
                        'protection_type': {
                            'type': 'string',
                            'allowed': ['ASYNC', 'SYNC']
                        },
                        'rpo': {
                            'type': 'integer'
                        },
                        'rpo_unit': {
                            'type': 'string',
                            'allowed': ['MINUTE', 'HOUR', 'DAY', 'WEEK']
                        },
                        'snapshot_type': {
                            'type': 'string',
                            'allowed': ['CRASH_CONSISTENT', 'APPLICATION_CONSISTENT']
                        },
                        'local_retention_policy': RETENTION_POLICY_SCHEMA,
                        'remote_retention_policy': RETENTION_POLICY_SCHEMA
                    }
                }
            }
        }
    }
}

SECURITY_POLICIES_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'app_rule': {
                'type': 'dict',
                'schema': {
                    'policy_mode': {
                        'type': 'string',
                        'allowed': ['MONITOR', 'APPLY']
                    },
                    'target_group': {
                        'type': 'dict',
                        'schema': {
                            'categories': {
                                'type': 'dict',
                                'schema': {
                                    'AppType': {'type': 'string'}
                                }
                            }
                        }
                    },
                    'inbounds': INBOUND_OUTBOUND_SCHEMA,
                    'outbounds': INBOUND_OUTBOUND_SCHEMA
                }
            },
            'allow_ipv6_traffic': {
                'type': 'boolean'
            },
            'hitlog': {
                'type': 'boolean'
            }
        }
    }
}

ADDRESS_GROUP_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'subnets': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'network_ip': {
                            'type': 'string',
                            'validator': validate_ip
                        },
                        'network_prefix': {
                            'type': 'integer'
                        }
                    }
                }
            }
        }
    }
}

SERVICE_GROUP_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'service_details': {
                'type': 'dict',
                'keyschema': {'type': 'string'},
                'valueschema': {
                    'type': 'list'
                }
            }
        }
    }
}

POD_CLUSTER_SCHEMA = {
    'required': True,
    'type': 'dict',
    'keyschema': {'type': 'string', 'validator': validate_ip},
    'valueschema': {
        'type': 'dict',
        'schema': {
            'name': {
                'type': 'string',
                'required': True,
            },
            'dsip': {
                'type': 'string',
                'required': True,
                'validator': validate_ip
            },
            'pe_username': USERNAME_PASSWORD_SCHEMA,
            'pe_password': USERNAME_PASSWORD_SCHEMA,
            'eula': EULA_SCHEMA,
            'enable_pulse': PULSE_SCHEMA,
            'directory_services': AD_SCHEMA,
            'networks': PE_NETWORKS_SCHEMA,
            'containers': PE_CONTAINERS_SCHEMA,
            'ncm_subnets': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'string'
                }
            },
            'ncm_users': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'string'
                }
            }
        }
    }
}

NKE_CUSTOM_NODE_CONFIG = {
    'type': 'dict',
    'schema': {
        'num_instances': {
            'type': 'integer'
        },
        'cpu': {
            'type': 'integer'
        },
        'memory_gb': {
            'type': 'integer'
        },
        'disk_gb': {
            'type': 'integer'
        }
    }
}

NKE_CLUSTER_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'cluster': {
                'type': 'dict',
                'schema': {
                    'name': {'type': 'string'}
                }
            },
            'name': {
                'type': 'string',
                'required': True,
            },
            'cluster_type': {
                'type': 'string',
                'required': True,
                'allowed': ['DEV', 'PROD']
            },
            'k8s_version': {
                'required': True,
                'type': ['float', 'string']
            },
            'host_os': {
                'required': True,
                'type': 'string'
            },
            'node_subnet': {
                'type': 'dict',
                'schema': {
                    'name': {'type': 'string'}
                }
            },
            'cni': {
                'type': 'dict',
                'schema': {
                    'node_cidr_mask_size': {
                        'type': 'integer'
                    },
                    'service_ipv4_cidr': {
                        'type': 'string',
                        'validator': validate_subnet
                    },
                    'pod_ipv4_cidr': {
                        'type': 'string',
                        'validator': validate_subnet
                    },
                    'network_provider': {
                        'type': 'string',
                        'allowed': ['Calico', 'Flannel']
                    }
                }
            },
            'custom_node_configs': {
                'type': 'dict',
                'schema': {
                    'etcd': NKE_CUSTOM_NODE_CONFIG,
                    'masters': NKE_CUSTOM_NODE_CONFIG,
                    'workers': NKE_CUSTOM_NODE_CONFIG
                }
            },
            'storage_class': {
                'type': 'dict',
                'schema': {
                    'pe_username': USERNAME_PASSWORD_SCHEMA,
                    'pe_password': USERNAME_PASSWORD_SCHEMA,
                    'default_storage_class': {'type': 'boolean'},
                    'name': {'type': 'string'},
                    'reclaim_policy': {
                        'type': 'string',
                        'allowed': ['Retain', 'Delete']
                    },
                    'storage_container': {'type': 'string'},
                    'file_system': {
                        'type': 'string',
                        'allowed': ['ext4', 'xfs']
                    },
                    'flash_mode': {'type': 'boolean'}
                }
            }
        }
    }
}

OBJECTS_SCHEMA = {
    'type': 'dict',
    'schema': {
        'objectstores': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'name': {'type': 'string', 'required': True},
                    'domain': {'type': 'string', 'required': True, 'validator': validate_domain},
                    'cluster': {'type': 'string', 'required': True},
                    'network': {'type': 'string', 'required': True},
                    'static_ip_list': {'type': 'list', 'required': True, 'validator': validate_ip_list},
                    'num_worker_nodes': {'type': 'integer', 'required': True},
                    'buckets': {
                        'type': 'list',
                        'schema': {
                            'type': 'dict',
                            'schema': {
                                'name': {'type': 'string', 'required': True},
                                'user_access_list': {
                                    'type': 'list',
                                    'required': True
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

POD_CONFIG_SCHEMA = {
    'pod': {
        'type': 'dict',
        'required': True,
        'schema': {
            'pod_name': {
                'type': 'string',
                'required': True
            },
            'pod_blocks': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'pod_block_name': {
                            'type': 'string',
                            'required': True
                        },
                        'pc_ip': {
                            'type': 'string',
                            'required': True,
                            'validator': validate_ip
                        },
                        'pc_username': USERNAME_PASSWORD_SCHEMA,
                        'pc_password': USERNAME_PASSWORD_SCHEMA,
                        'ncm_vm_ip': {
                            'type': 'string',
                            'required': True,
                            'validator': validate_ip
                        },
                        'ncm_account': {
                            'type': 'dict',
                            'required': False,
                            'schema': {
                                'name': {
                                    'type': 'string',
                                    'required': True
                                },
                                'sync_interval_seconds': {
                                    'type': 'integer',
                                    'required': True
                                },
                                'pc_ip': {
                                    'type': 'string',
                                    'required': True
                                },
                                'pc_username': USERNAME_PASSWORD_SCHEMA,
                                'pc_password': USERNAME_PASSWORD_SCHEMA,
                            }
                        },
                        'ncm_username': USERNAME_PASSWORD_SCHEMA,
                        'ncm_password': USERNAME_PASSWORD_SCHEMA,
                        'objects': OBJECTS_SCHEMA,
                        'remote_azs': REMOTE_AZS_SCHEMA,
                        'protection_rules': PROTECTION_RULES_SCHEMA,
                        'recovery_plans': RECOVERY_PLAN_SCHEMA,
                        'categories': PC_CATEGORIES_SCHEMA,
                        'address_groups': ADDRESS_GROUP_SCHEMA,
                        'service_groups': SERVICE_GROUP_SCHEMA,
                        'security_policies': SECURITY_POLICIES_SCHEMA,
                        'edge_sites': {
                            'type': 'list',
                            'required': True,
                            'schema': {
                                'type': 'dict',
                                'schema': {
                                    'site_name': {
                                        'type': 'string',
                                        'required': True
                                    },
                                    'clusters': POD_CLUSTER_SCHEMA,
                                    'nke_clusters': NKE_CLUSTER_SCHEMA
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

CREATE_VM_WORKLOAD_SCHEMA = {
    'ncm_vm_ip': {
        'required': True,
        'type': 'string',
        'validator': validate_ip
    },
    'ncm_username': {
        'required': True,
        'type': 'string',
        'validator': contains_whitespace
    },
    'ncm_password': {
        'required': True,
        'type': 'string'
    },
    'bp_list': {
        'required': True,
        'empty': False,
        'type': 'list',
        'schema': {
            'type': 'dict',
            'empty': False,
            'schema': {
                'dsl_file': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'name': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'app_name': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'runtime_vars': {
                    'required': False,
                    'type': 'string',
                }
            }
        }
    },
    'projects': {
        'required': True,
        'empty': False,
        'type': 'list',
        'schema': {
            'type': 'dict',
            'empty': False,
            'schema': {
                'PROJECT_NAME': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'CLUSTER_NAME': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'SUBNET_NAME': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'ACCOUNT_NAME': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                }
            }
        }
    }
}

CREATE_AI_WORKLOAD_SCHEMA = {
    'pc_ip': {
        'required': True,
        'type': 'string',
        'validator': validate_ip
    },
    'pc_username': {
        'required': True,
        'type': 'string',
        'validator': contains_whitespace
    },
    'pc_password': {
        'required': True,
        'type': 'string'
    },
    'site_name': {
        'required': True,
        'empty': False,
        'type': 'string'
    },
    'project_name': {
        'required': True,
        'empty': False,
        'type': 'string'
    },
    'account_name': {
        'required': True,
        'empty': False,
        'type': 'string'
    },
    'subnets': {
        'required': True,
        'empty': False,
        'type': 'dict'
    },
    'bp_list': {
        'required': True,
        'empty': False,
        'type': 'list',
        'schema': {
            'type': 'dict',
            'empty': False,
            'schema': {
                'dsl_file': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'name': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'app_name': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'cluster': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'subnet': {
                    'required': True,
                    'empty': False,
                    'type': 'string',
                },
                'variable_list': {
                    'required': False,
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'value': {
                                'required': True,
                                'type': 'dict',
                                'schema': {
                                    'value': {
                                        'required': True,
                                        'empty': False,
                                        'type': 'string',
                                    }
                                }
                            },
                            'context': {
                                'required': True,
                                'empty': False,
                                'type': 'string',
                            },
                            'name': {
                                'required': True,
                                'empty': False,
                                'type': 'string',
                            }
                        }
                    }
                }
            }
        }
    }
}

OVA_UPLOAD_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'url': {
                'type': 'string',
                'required': True
            },
            'name': {
                'type': 'string',
                'required': True
            },
            'cluster_name_list': {
                'type': 'list',
                'required': True
            }
        }
    }
}

IMAGE_UPLOAD_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'url': {
                'type': 'string',
                'required': True
            },
            'name': {
                'type': 'string',
                'required': True
            },
            'cluster_name_list': {
                'type': 'list',
                'required': True
            },
            'image_type': {
                'type': 'string',
                'required': True,
                'allowed': ['DISK_IMAGE', 'ISO_IMAGE']
            }
        }
    }
}

DEPLOY_OVA_AS_VM_SCHEMA = {
    'type': 'list',
    'schema': {
        'type': 'dict',
        'schema': {
            'cluster_name': {
                'type': 'string',
                'required': True
            },
            'ova_name': {
                'type': 'string',
                'required': True
            },
            'vm_spec_list': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'vm_name': {
                            'type': 'string',
                            'required': True
                        },
                        'subnet_name': {
                            'type': 'string',
                            'required': True
                        }
                    }
                }
            }
        }
    }
}

DEPLOY_PC_FILES_SCHEMA = {
    'type': 'dict',
    'schema': {
        'file_url': {
            'type': 'string',
            'required': True
        },
        'metadata_file_url': {
            'type': 'string',
            'required': True
        },
        'pc_version': {
            'type': 'string',
            'required': True
        },
        'md5sum': {
            'type': 'string',
            'required': False
        }
    }
}

DEPLOY_PC_CONFIG_SCHEMA = {
    'type': 'dict',
    'schema': {
        'file_url': {
            'type': 'string',
            'required': True
        },
        'metadata_file_url': {
            'type': 'string',
            'required': True
        },
        'pc_version': {
            'type': 'string',
            'required': True
        },
        'md5sum': {
            'type': 'string',
            'required': False
        },
        'pc_vm_name_prefix': {
            'type': 'string',
            'required': True,
            'validator': contains_whitespace
        },
        'num_pc_vms': {
            'type': 'integer',
            'required': True,
            'allowed': [1,3]
        },
        'pc_size': {
            'type': 'string',
            'required': True,
            'allowed': ['small', 'large', 'xlarge']
        },
        'pc_vip': {
            'type': 'string',
            'required': True,
            'validator': validate_ip
        },
        'ip_list': {
            'type': 'list',
            'required': True,
            'validator': validate_ip_list
        },
        'ntp_server_list': {
            'type': 'list',
            'required': False
        },
        'dns_server_ip_list': {
            'type': 'list',
            'required': True,
        },
        'container_name': {
            'type': 'string',
            'required': True
        },
        'network_name': {
            'type': 'string',
            'required': True
        },
        'default_gateway': {
            'type': 'string',
            'required': True,
            'validator': validate_ip
        },
        'subnet_mask': {
            'type': 'string',
            'required': True,
            'validator': validate_ip
        },
        'delete_existing_software': {
            'type': 'boolean'
        }
    }
}

POD_MANAGEMENT_DEPLOY_SCHEMA = {
    'pod': {
        'type': 'dict',
        'required': True,
        'schema': {
            'pod_name': {
                'type': 'string',
                'required': True
            },
            'pc_ip': {
                'type': 'string',
                'required': True,
                'validator': validate_ip
            },
            'pc_username': USERNAME_PASSWORD_SCHEMA,
            'pc_password': USERNAME_PASSWORD_SCHEMA,
            'ovas': OVA_UPLOAD_SCHEMA,
            'images': IMAGE_UPLOAD_SCHEMA,
            'ncm': DEPLOY_OVA_AS_VM_SCHEMA,
            'clusters': {
                'type': 'dict',
                'keyschema': {'type': 'string', 'validator': validate_ip},
                'valueschema': {
                    'type': 'dict',
                    'schema': {
                        'pe_username': USERNAME_PASSWORD_SCHEMA,
                        'pe_password': USERNAME_PASSWORD_SCHEMA,
                        'cvm_username': USERNAME_PASSWORD_SCHEMA,
                        'cvm_password': USERNAME_PASSWORD_SCHEMA,
                        'deploy_pc_config': DEPLOY_PC_CONFIG_SCHEMA
                    }
                }
            }
        }
    }
}

POD_MANAGEMENT_CONFIG_SCHEMA = {
    'pod': {
        'type': 'dict',
        'required': True,
        'schema': {
            'pod_name': {
                'type': 'string',
                'required': True
            },
            'pod_blocks': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'pod_block_name': {
                            'type': 'string'
                        },
                        'pc_ip': {
                            'type': 'string',
                            'required': True,
                            'validator': validate_ip
                        },
                        'pc_username': USERNAME_PASSWORD_SCHEMA,
                        'pc_password': USERNAME_PASSWORD_SCHEMA,
                        'eula': EULA_SCHEMA,
                        'enable_pulse': PULSE_SCHEMA,
                        'enable_fc': PULSE_SCHEMA,
                        'generate_fc_api_key': PULSE_SCHEMA,
                        'fc_alias_key_name': {'type': 'string'},
                        'clusters': {
                            'type': 'dict',
                            'keyschema': {'type': 'string', 'validator': validate_ip},
                            'valueschema': {
                                'type': 'dict',
                                'schema': {
                                    'pe_username': USERNAME_PASSWORD_SCHEMA,
                                    'pe_password': USERNAME_PASSWORD_SCHEMA
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
