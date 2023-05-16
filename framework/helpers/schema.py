from .general_utils import validate_ip, contains_whitespace, validate_domain, validate_ip_list

"""
We are using a popular Python library "cerberus" to define the json/ yml schema
https://docs.python-cerberus.org/en/stable/validation-rules.html
"""

GLOBAL_NETWORK_SCHEMA = {
    'global_network': {
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
}

IMAGING_SCHEMA = {
    'pc_ip': {
        'type': 'string',
        'required': True,
        'validator': validate_ip
    },
    'pc_username': {
        'required': True,
        'type': 'string',
        'validator': contains_whitespace
    },
    'pc_password': {
        'required': True,
        'type': 'string',
        'validator': contains_whitespace
    },
    'site_name': {
        'required': True,
        'type': 'string'
    },
    'blocks_serial_numbers': {
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
    "imaging_parameters": {
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
    'network': {
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
    },
    'clusters': {
        'required': True,
        'type': 'dict',
        "keyschema": {"type": "string"},
        "valueschema": {
            "type": "dict",
            "schema": {
                "cluster_size": {
                    'type': 'integer',
                    'required': True,
                },
                "cluster_vip": {
                    'type': 'string',
                    'required': True,
                    'validator': validate_ip
                },
                "cvm_ram": {
                    'type': 'integer',
                    'required': True,
                    'min': 12
                },
                "redundancy_factor": {
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
                'network': {
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
                },
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
    },
}

IMAGING_SCHEMA.update(GLOBAL_NETWORK_SCHEMA)

USERNAME_PASSWORD_SCHEMA = {
    'required': True,
    'type': 'string',
    'validator': contains_whitespace
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
            'allowed': ["ACTIVE_DIRECTORY"],
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

PE_CONTAINERS = {
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

PE_NETWORKS = {
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

POD_REMOTE_AZS = {
    'type': 'dict',
    "keyschema": {"type": "string"},
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

POD_CATEGORIES_SCHEMA = {
    "type": "list",
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

POD_RECOVERY_PLAN_SCHEMA = {
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
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "primary": {
                            "type": "dict",
                            "schema": {
                                "test": {
                                    "type": "dict",
                                    'schema': {
                                        'name': {'type': 'string'},
                                        'gateway_ip': {
                                            'type': 'string',
                                            'validator': validate_ip
                                        },
                                        'prefix': {'type': 'integer'}
                                    }
                                },
                                "prod": {
                                    "type": "dict",
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
                        "recovery": {
                            "type": "dict",
                            "schema": {
                                "test": {
                                    "type": "dict",
                                    'schema': {
                                        'name': {'type': 'string'},
                                        'gateway_ip': {
                                            'type': 'string',
                                            'validator': validate_ip
                                        },
                                        'prefix': {'type': 'integer'}
                                    }
                                },
                                "prod": {
                                    "type": "dict",
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

POD_RETENTION_POLCY = {
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

POD_PROTECTION_RULES_SCHEMA = {
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
                                'cluster': {
                                    'type': 'string'
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
                            'allowed': ["ASYNC", "SYNC"]
                        },
                        'rpo': {
                            'type': 'integer'
                        },
                        'rpo_unit': {
                            'type': 'string',
                            'allowed': ["MINUTE", "HOUR", "DAY", "WEEK"]
                        },
                        'snapshot_type': {
                            'type': 'string',
                            'allowed': ["CRASH_CONSISTENT", "APPLICATION_CONSISTENT"]
                        },
                        "local_retention_policy": POD_RETENTION_POLCY,
                        "remote_retention_policy": POD_RETENTION_POLCY
                    }
                }
            }
        }
    }
}

POD_SECURITY_POLICIES_SCHEMA = {
    "type": "list",
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
                        'allowed': ["MONITOR", "APPLY"]
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

POD_ADDRESS_GROUP_SCHEMA = {
    "type": "list",
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

POD_SERVICE_GROUP_SCHEMA = {
    "type": "list",
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
    "keyschema": {"type": "string"},
    "valueschema": {
        "type": "dict",
        "schema": {
            "name": {
                'type': 'string',
                'required': True,
            },
            "dsip": {
                'type': 'string',
                'required': True,
                'validator': validate_ip
            },
            'pe_username': USERNAME_PASSWORD_SCHEMA,
            'pe_password': USERNAME_PASSWORD_SCHEMA,
            'eula': EULA_SCHEMA,
            'enable_pulse': PULSE_SCHEMA,
            'directory_services': AD_SCHEMA,
            'networks': PE_NETWORKS,
            'containers': PE_CONTAINERS
        }
    }
}

POD_CONFIG_SCHEMA = {
    'pods': {
        'type': 'list',
        'required': True,
        'schema': {
            'type': 'dict',
            'valueschema': {
                'type': 'dict',
                'schema': {
                    'pc_ip': {
                        'type': 'string',
                        'required': True,
                        'validator': validate_ip
                    },
                    'pc_username': USERNAME_PASSWORD_SCHEMA,
                    'pc_password': USERNAME_PASSWORD_SCHEMA,
                    'remote_azs': POD_REMOTE_AZS,
                    'protection_rules': POD_PROTECTION_RULES_SCHEMA,
                    'recovery_plans': POD_RECOVERY_PLAN_SCHEMA,
                    "categories": POD_CATEGORIES_SCHEMA,
                    "address_groups": POD_ADDRESS_GROUP_SCHEMA,
                    "service_groups": POD_SERVICE_GROUP_SCHEMA,
                    "security_policies": POD_SECURITY_POLICIES_SCHEMA,
                    'clusters': POD_CLUSTER_SCHEMA
                }
            }
        }
    }
}

CREATE_VM_WORKLOAD_SCHEMA = {
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
