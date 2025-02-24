from framework.helpers.general_utils import validate_ip, contains_whitespace, validate_domain, validate_subnet, \
    validate_dsip, validate_netmask

"""
We are using a popular Python library "cerberus" to define the json/ yml schema
https://docs.python-cerberus.org/validation-rules.html
"""

# todo add dependencies to schema
DNS_SCHEMA = {
    'name_servers_list': {
        'type': 'list'
    }
}

NTP_SCHEMA = {
    'ntp_servers_list': {
        'type': 'list'
    }
}

CREDENTIAL_SCHEMA = {
    'type': 'string',
    'validator': contains_whitespace
}

CALM_CREDS_SCHEMA = {
    'type': 'string',
    'validator': contains_whitespace
}

IMAGING_NETWORK = {
    'type': 'dict',
    'required': False,
    'schema': {
        # either subnet or netmask need to be provided
        'host_subnet': {
            'required': False,
            'empty': True,
            'type': 'string',
            'validator': validate_subnet
        },
        'host_netmask': {
            'required': False,
            'empty': True,
            'type': 'string',
            'validator': validate_netmask
        },
        'host_gateway': {
            'required': True,
            'empty': True,
            'type': 'string',
            'validator': validate_ip
        },
        'ipmi_subnet': {
            'required': False,
            'type': 'string',
            'empty': True,
            'validator': validate_subnet
        },
        'ipmi_netmask': {
            'required': False,
            'empty': True,
            'type': 'string',
            'validator': validate_netmask
        },
        'ipmi_gateway': {
            'required': True,
            'empty': True,
            'type': 'string',
            'validator': validate_ip
        },
        'domain': {
            'required': True,
            'type': 'string',
            'empty': True,
            'default': '',
            'schema': {
                'type': 'string',
                'validator': validate_domain
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
                        'pc_credential': CREDENTIAL_SCHEMA,
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
                                    'use_existing_network_settings': {
                                        'required': False,
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
                                            'aos_url': {
                                                'required': True,
                                                'type': 'string'
                                            },
                                            'hypervisor_type': {
                                                'required': True,
                                                'type': 'string',
                                                'allowed': ['kvm', 'esx', 'hyperv']
                                            },
                                            'hypervisor_url': {
                                                'type': 'string'
                                            }
                                        }
                                    },
                                    'ntp_servers_list': {
                                        'type': 'list',
                                        'required': False
                                    },
                                    'name_servers_list': {
                                        'type': 'list',
                                        'required': True
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
                                                    'required': False,
                                                    'validator': validate_ip
                                                },
                                                'cvm_ram': {
                                                    'type': 'integer',
                                                    'required': False,
                                                    'min': 12
                                                },
                                                'redundancy_factor': {
                                                    'type': 'integer',
                                                    'required': True,
                                                    'allowed': [2, 3]
                                                },
                                                'node_details': {
                                                    'type': 'list',
                                                    'required': False,
                                                    'schema': {
                                                        'type': 'dict',
                                                        'schema': {
                                                            'node_serial': {
                                                                'type': 'string',
                                                                'required': True,
                                                                'validator': contains_whitespace
                                                            },
                                                            'cvm_ip': {
                                                                'type': 'string',
                                                                'required': False,
                                                                'validator': validate_ip
                                                            },
                                                            'host_ip': {
                                                                'type': 'string',
                                                                'required': False,
                                                                'validator': validate_ip
                                                            },
                                                            'ipmi_ip': {
                                                                'type': 'string',
                                                                'required': False,
                                                                'validator': validate_ip
                                                            },
                                                            'hypervisor_hostname': {
                                                                'type': 'string',
                                                                'required': False,
                                                                'validator': contains_whitespace
                                                            }
                                                        }
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
    }
}

EULA_SCHEMA = {
    'eula': {
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
}

PULSE_SCHEMA = {
    'enable_pulse': {'type': 'boolean'}
}

HA_RESERVATION_SCHEMA = {
    'ha_reservation': {
        'type': 'dict',
        'schema': {
            'enable_failover': {'type': 'boolean', 'required': True},
            'num_host_failure_to_tolerate': {'type': 'integer', 'required': True}
        }
    }
}

REBUILD_RESERVATION_SCHEMA = {
    'enable_rebuild_reservation': {'type': 'boolean'}
}

AD_CREATE_SCHEMA = {
    'directory_services': {
        'type': 'dict',
        'required': False,
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
            'ad_directory_url': {
                'type': 'string',
                'required': True,
                'empty': False,
            },
            'service_account_credential': {
                'type': 'string',
                'required': True,
                'empty': False,
                'validator': contains_whitespace
            },
            'role_mappings': {
                'type': 'list',
                'required': False,
                'dependencies': ['ad_name'],
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'role_type': {
                            'required': True,
                            'type': 'string',
                            'allowed': ['ROLE_CLUSTER_ADMIN', 'ROLE_USER_ADMIN', 'ROLE_CLUSTER_VIEWER',
                                        'ROLE_BACKUP_ADMIN']
                        },
                        'entity_type': {
                            'required': True,
                            'type': 'string',
                            'allowed': ['GROUP', 'OU', 'USER']
                        },
                        'values': {
                            'required': True,
                            'type': 'list',
                            'schema': {
                                'type': 'string'
                            }
                        }
                    }
                }
            }
        }}
}

AD_DELETE_SCHEMA = {
    'directory_services': {
        'type': 'dict',
        'required': False,
        'schema': {
            'ad_name': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'role_mappings': {
                'type': 'list',
                'required': False,
                'dependencies': ['ad_name'],
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'role_type': {
                            'required': True,
                            'type': 'string',
                            'allowed': ['ROLE_CLUSTER_ADMIN', 'ROLE_USER_ADMIN', 'ROLE_CLUSTER_VIEWER',
                                        'ROLE_BACKUP_ADMIN']
                        },
                        'entity_type': {
                            'required': True,
                            'type': 'string',
                            'allowed': ['GROUP', 'OU', 'USER']
                        },

                    }
                }
            }
        }}
}

IDP_CREATE_SCHEMA = {
    'saml_idp_configs': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True,
                    'empty': False
                },
                'username_attr': {
                    'type': 'string',
                },
                'email_attr': {
                    'type': 'string',
                },
                'groups_attr': {
                    'type': 'string',
                },
                'groups_delim': {
                    'type': 'string',
                },
                'metadata_path': {
                    'type': 'string',
                },
                'metadata_url': {
                    'type': 'string',
                },
                'idp_properties': {
                    'type': 'dict',
                    'schema': {
                        'idp_url': {
                            'required': True,
                            'type': 'string'
                        },
                        'login_url': {
                            'required': True,
                            'type': 'string'
                        },
                        'logout_url': {
                            'required': True,
                            'type': 'string'
                        },
                        'error_url': {
                            'type': 'string'
                        },
                        'certificate': {
                            'required': True,
                            'type': 'string'
                        }

                    }
                }
            }
        }
    }
}

CONTAINERS_CREATE_SCHEMA = {
    'containers': {
        'type': 'list',
        'required': False,
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
                    'required': True
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
        }}
}

CONTAINERS_DELETE_SCHEMA = {
    'containers': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True
                },
            }
        }
    }}

# todo : Networks Also There for PC
NETWORKS_CREATE_SCHEMA = {
    'networks': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'required': False,
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True,
                },
                'vlan_id': {
                    'required': True,
                    'type': 'integer',
                },
                'ip_config': {
                    'required': False,
                    'type': 'dict',
                    'schema': {
                        'network_ip': {
                            'type': 'string',
                            'required': True,
                            'validator': validate_ip
                        },
                        'network_prefix': {
                            'required': True,
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
                                    'schema': {
                                        'type': 'string',
                                        'validator': validate_ip
                                    }
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
        }
    }}

NETWORKS_DELETE_SCHEMA = {
    'networks': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'vlan_id': {
                    'type': 'integer',
                    'required': True
                },
                'name': {
                    'type': 'string',
                },
                'managed': {
                    'type': 'boolean'
                },
                'ip_config':
                    {
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
                        }
                    }
            }
        }
    }}

REMOTE_AZS_CONNECT_SCHEMA = {
    'remote_azs': {
        'type': 'dict',
        'required': False,
        'keyschema': {'type': 'string', 'validator': validate_ip},
        'valueschema': {
            'type': 'dict',
            'schema': {
                'pc_credential': {
                    'type': 'string',
                    'required': True,
                    'validator': contains_whitespace
                }
            }
        }
    }}

REMOTE_AZS_DISCONNECT_SCHEMA = {
    'remote_azs': {
        'type': 'list',
        'required': False,
        'schema': {'type': 'string', 'required': True, 'validator': validate_ip}
    }}

CATEGORIES_CREATE_SCHEMA = {
    'categories': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'description': {'type': 'string'},
                'values': {
                    'type': 'list',
                    'required': True,
                    'schema': {
                        'type': 'string'
                    }
                }
            }
        }
    }
}

CATEGORIES_DELETE_SCHEMA = {
    'categories': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'values': {
                    'type': 'list',
                    'schema': {'type': 'string', 'required': True}
                },
                'delete_only_values': {
                    'type': 'boolean',
                    'required': False,
                    'dependencies': 'values',
                    'default': False
                }
            }
        }}
}

RECOVERY_PLAN_CREATE_SCHEMA = {
    'recovery_plans': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True
                },
                'desc': {
                    'type': 'string'
                },
                'primary_location': {
                    'type': 'dict',
                    'required': True,
                    'schema': {
                        'availability_zone': {
                            'type': 'string',
                            'required': True,
                            'validator': validate_ip
                        },
                    }
                },
                'recovery_location': {
                    'type': 'dict',
                    'required': True,
                    'schema': {
                        'availability_zone': {
                            'type': 'string',
                            'validator': validate_ip,
                            'required': True
                        },
                    }
                },
                'stages': {
                    'type': 'list',
                    'required': True,
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'vms': {
                                'type': 'list',
                                'schema': {
                                    'type': 'dict',
                                    'schema': {
                                        'name': {'type': 'string', 'required': True},
                                        'enable_script_exec': {'type': 'boolean', 'required': True},
                                        'delay': {'type': 'integer', 'required': True}
                                    }
                                }
                            },
                            'categories': {
                                'type': 'list',
                                'schema': {
                                    'type': 'dict',
                                    'schema': {
                                        'key': {'type': 'string', 'required': True},
                                        'value': {'type': 'string', 'required': True}
                                    }
                                }
                            }
                        }
                    }
                },
                'network_type': {
                    'type': 'string',
                    'required': False,
                    'allowed': ['NON_STRETCH', 'STRETCH']
                },
                'network_mappings': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'primary': {
                                'type': 'dict',
                                'required': True,
                                'schema': {
                                    'test': {
                                        'type': 'dict',
                                        'schema': {
                                            'name': {'type': 'string', 'required': True},
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
                                            'name': {'type': 'string', 'required': True},
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
                                'required': True,
                                'schema': {
                                    'test': {
                                        'type': 'dict',
                                        'schema': {
                                            'name': {'type': 'string', 'required': True},
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
                                            'name': {'type': 'string', 'required': True},
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
}

RECOVERY_PLAN_DELETE_SCHEMA = {
    'recovery_plans': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'required': True,
            'schema': {
                'name': {
                    'type': 'string'
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
            'required': False,
            'schema': {
                'snapshot_interval_type': {
                    'type': 'string',
                    'required': True,
                    'allowed': ['HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
                },
                'multiple': {'type': 'integer', 'required': True}
            }
        }
    }
}

PROTECTION_RULES_CREATE_SCHEMA = {
    'protection_rules': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True
                },
                'desc': {
                    'type': 'string'
                },
                'protected_categories': {
                    'type': 'dict',
                    'required': True,
                    'keyschema': {'type': 'string'},
                    'valueschema': {
                        'type': 'list'
                    }
                },
                'schedules': {
                    'type': 'list',
                    'required': True,
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'source': {
                                'schema': {
                                    'availability_zone': {
                                        'type': 'string',
                                        'required': True,
                                        'validator': validate_ip
                                    },
                                    'clusters': {
                                        'type': 'list',
                                        'required': True
                                    }
                                }
                            },
                            'destination': {
                                'type': 'dict',
                                'required': True,
                                'schema': {
                                    'availability_zone': {
                                        'type': 'string',
                                        'validator': validate_ip,
                                        'required': True
                                    },
                                    'cluster': {
                                        'type': 'string',
                                        'required': True
                                    }
                                }
                            },
                            'protection_type': {
                                'type': 'string',
                                'required': True,
                                'allowed': ['ASYNC', 'SYNC']
                            },
                            'rpo': {
                                'type': 'integer',
                                'required': True
                            },
                            'rpo_unit': {
                                'type': 'string',
                                'required': True,
                                'allowed': ['MINUTE', 'HOUR', 'DAY', 'WEEK']
                            },
                            'snapshot_type': {
                                'type': 'string',
                                'required': True,
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
}

PROTECTION_RULES_DELETE_SCHEMA = {
    'protection_rules': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string'
                }
            }
        }
    }
}

SECURITY_POLICIES_CREATE_SCHEMA = {
    'security_policies': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'description': {'type': 'string', 'required': False},
                'type': {
                    'type': 'string',
                    'required': True,
                    'allowed': ['APPLICATION', 'QUARANTINE', 'ISOLATION']
                },
                'allow_ipv6_traffic': {
                    'type': 'boolean',
                    'required': False
                },
                'hitlog': {
                    'type': 'boolean',
                    'required': True
                },
                'policy_mode': {
                    'type': 'string',
                    'required': True,
                    'allowed': ['ENFORCE', 'MONITOR', 'SAVE']
                },
                'app_rule': {
                    'type': 'list',
                    'required': False,
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'description': {'type': 'string', 'required': False},
                            'target_group': {
                                'type': 'dict',
                                'required': True,
                                'schema': {
                                    'categories': {
                                        'type': 'list',
                                        'required': True,
                                        'schema': {'type': 'dict'}
                                    },
                                    'intra_group': {
                                        'type': 'boolean',
                                        'required': False
                                    }
                                }
                            },
                            'inbounds': {
                                'type': 'dict',
                                'required': False,
                                'schema': {
                                    'allow_all': {'type': 'boolean', 'required': False},
                                    'allow_none': {'type': 'boolean', 'required': False},
                                    'descpription': {'type': 'string', 'required': False},
                                    'address': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {
                                            'type': 'dict',
                                            'schema': {
                                                'name': {'type': 'string', 'required': True}
                                            }
                                            }
                                    },
                                    'subnet': {
                                        'type': 'string',
                                        'required': False,
                                        'validator': validate_subnet},

                                    'categories': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {'type': 'dict'}
                                    }
                                }
                            },
                            'outbounds': {
                                'type': 'dict',
                                'required': False,
                                'schema': {
                                    'descpription': {'type': 'string', 'required': False},
                                    'address': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {
                                            'type': 'dict',
                                            'schema': {
                                                'name': {'type': 'string', 'required': True}
                                            }
                                            }
                                    },
                                    'subnet': {
                                        'type': 'string',
                                        'required': False,
                                        'validator': validate_subnet},

                                    'categories': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {'type': 'dict'}
                                    }
                                }
                            },
                            'services': {
                                'type': 'dict',
                                'required': False,
                                'schema': {
                                    'udp': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {
                                            'type': 'dict',
                                            'schema': {
                                                'start_port': {'type': 'integer', 'required': True},
                                                'end_port': {'type': 'integer', 'required': True}
                                            }
                                        }
                                    },
                                    'tcp': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {
                                            'type': 'dict',
                                            'schema': {
                                                'start_port': {'type': 'integer', 'required': True},
                                                'end_port': {'type': 'integer', 'required': True}
                                            }
                                        }
                                    },
                                    'icmp': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {
                                            'type': 'dict',
                                            'schema': {
                                                'type': {'type': 'integer', 'required': True},
                                                'code': {'type': 'integer', 'required': True}
                                            }
                                        }
                                    },
                                    'service_group': {
                                        'type': 'list',
                                        'required': False,
                                        'schema': {
                                            'type': 'dict',
                                                'schema': {'name': {'type':'string'}}
                                        }
                                    },
                                    'all': {
                                        'type': 'boolean',
                                        'required': False
                                    }
                                }
                            }
                        }
                    }
                },
                'two_env_isolation_rule': {
                    'type': 'dict',
                    'required': False,
                    'schema': {
                        'first_isolation_group': {
                            'type': 'list',
                            'required': True,
                            'schema': {'type': 'dict'}
                        },
                        'second_isolation_group': {
                            'type': 'list',
                            'required': True,
                            'schema': {'type': 'dict'}
                        }
                    }
                }
            }
        }
    }
}


SECURITY_POLICIES_CREATE_SCHEMA_v3 = {
    'security_policies': {
        'type': 'list',
        'required': False,
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'description': {'type': 'string'},
                'app_rule': {
                    'type': 'dict',
                    'schema': {
                        'policy_mode': {
                            'type': 'string',
                            'required': True,
                            'allowed': ['MONITOR', 'APPLY']
                        },
                        'target_group': {
                            'type': 'dict',
                            'schema': {
                                'categories': {
                                    'type': 'dict',
                                    'required': True,
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
}

SECURITY_POLICIES_DELETE_SCHEMA = {
    'security_policies': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string'}
            }
        }
    }
}

ADDRESS_GROUP_CREATE_SCHEMA = {
    "address_groups": {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'description': {'type': 'string'},
                'subnets': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'required': True,
                        'schema': {
                            'network_ip': {
                                'type': 'string',
                                'required': True,
                                'validator': validate_ip
                            },
                            'network_prefix': {
                                'type': 'integer',
                                'required': True
                            }
                        }
                    }
                }
            }
        }
    }
}

ADDRESS_GROUP_DELETE_SCHEMA = {
    "address_groups": {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string'},
                'required': True
            }
        }
    }
}

SERVICE_GROUP_CREATE_SCHEMA = {
    'service_groups': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'description': {'type': 'string'},
                'service_details': {
                    'type': 'dict',
                    'required': True,
                    'keyschema': {'type': 'string'},
                    'valueschema': {
                        'type': 'list'
                    }
                }
            }
        }
    }
}

SERVICE_GROUP_DELETE_SCHEMA = {
    'service_groups': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'required': True,
            'schema': {
                'name': {'type': 'string'},
            }
        }
    }
}

CLUSTER_SCHEMA = {
    'clusters':
        {
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
                        'validator': validate_dsip
                    },
                    'pe_credential': CREDENTIAL_SCHEMA,
                    'new_admin_credential': CREDENTIAL_SCHEMA,
                    **EULA_SCHEMA,
                    **PULSE_SCHEMA,
                    **AD_CREATE_SCHEMA,
                    **NETWORKS_CREATE_SCHEMA,
                    **CONTAINERS_CREATE_SCHEMA,
                    **HA_RESERVATION_SCHEMA,
                    **REBUILD_RESERVATION_SCHEMA,
                    'ncm_subnets': {
                        'type': 'list',
                        'schema': {
                            'type': 'string'
                        }
                    },
                    'ncm_users': {
                        'type': 'list',
                        'schema': {
                            'type': 'string'
                        }
                    },
                    **DNS_SCHEMA,
                    **NTP_SCHEMA,
                    'skip_pc_registration': {
                        'type': 'boolean',
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
                    'pe_credential': CREDENTIAL_SCHEMA,
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

OBJECTS_CREATE_SCHEMA = {
    'objects': {
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
                        'storage_network': {'type': 'string', 'required': True},
                        'public_network': {'type': 'string', 'required': True},
                        'static_ip_list': {'type': 'list', 'required': True,
                                           'schema': {'type': 'string', 'validator': validate_ip}},
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
}

OBJECTS_DELETE_SCHEMA = {
    'objects': {
        'type': 'dict',
        'schema': {
            'objectstores': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'name': {'type': 'string', 'required': True},
                    }
                }
            }
        }
    }
}

PC_SCHEMA = {
    'pc_ip': {
        'required': False,
        'type': 'string',
        'validator': validate_ip
    },
    'pc_credential': CREDENTIAL_SCHEMA,
    **AD_CREATE_SCHEMA,
    **IDP_CREATE_SCHEMA,
    **EULA_SCHEMA,
    **PULSE_SCHEMA,
    **DNS_SCHEMA,
    **NTP_SCHEMA,
    'ncm_vm_ip': {
        'type': 'string',
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
            'pc_credential': CREDENTIAL_SCHEMA,
        }
    },
    'ncm_credential': CREDENTIAL_SCHEMA,
    **OBJECTS_CREATE_SCHEMA,
    **REMOTE_AZS_CONNECT_SCHEMA,
    **PROTECTION_RULES_CREATE_SCHEMA,
    **RECOVERY_PLAN_CREATE_SCHEMA,
    **CATEGORIES_CREATE_SCHEMA,
    **ADDRESS_GROUP_CREATE_SCHEMA,
    **SERVICE_GROUP_CREATE_SCHEMA,
    **SECURITY_POLICIES_CREATE_SCHEMA,
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
                        **PC_SCHEMA,
                        'edge_sites': {
                            'type': 'list',
                            'required': False,
                            'schema': {
                                'type': 'dict',
                                'schema': {
                                    'site_name': {
                                        'type': 'string',
                                        'required': True
                                    },
                                    **CLUSTER_SCHEMA,
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
    'ncm_credential': {
        'required': True,
        'type': 'string',
        'validator': contains_whitespace
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
    'pc_credential': {
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
    'ovas': {
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
}

OVA_DELETE_SCHEMA = {
    'ovas': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True
                }
            }
        }
    }
}

PC_IMAGE_UPLOAD_SCHEMA = {
    "images": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "url": {
                    "type": "string",
                    "required": True
                },
                "name": {
                    "type": "string",
                    "required": True
                },
                "cluster_name_list": {
                    "type": "list",
                    "required": True
                },
                "image_type": {
                    "type": "string",
                    "required": True,
                    "allowed": ["DISK_IMAGE", "ISO_IMAGE"]
                }
            }
        }
    }
}

PE_IMAGE_UPLOAD_SCHEMA = {
    "images": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "url": {
                    "type": "string",
                    "required": True
                },
                "name": {
                    "type": "string",
                    "required": True
                },
                "container_name": {
                    "type": "string",
                    "required": True
                },
                "image_type": {
                    "type": "string",
                    "required": True,
                    "allowed": ["DISK_IMAGE", "ISO_IMAGE"]
                }
            }
        }
    }
}

IMAGE_DELETE_SCHEMA = {
    'images': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': {
                    'type': 'string',
                    'required': True
                }
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
    'clusters': {
        'type': 'dict',
        'keyschema': {'type': 'string', 'validator': validate_ip},
        'valueschema': {
            'type': 'dict',
            'schema': {
                'pe_credential': CREDENTIAL_SCHEMA,
                'cvm_credential': CREDENTIAL_SCHEMA,
                'pc_configs': {
                    'required': True,
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'file_url': {
                                'type': 'string',
                            },
                            'metadata_file_url': {
                                'type': 'string',
                            },
                            'pc_version': {
                                'type': 'string',
                                'required': True
                            },
                            'md5sum': {
                                'type': 'string',
                            },
                            'pc_vm_name_prefix': {
                                'type': 'string',
                                'required': True,
                                'validator': contains_whitespace
                            },
                            'num_pc_vms': {
                                'type': 'integer',
                                'required': True,
                                'allowed': [1, 3]
                            },
                            'pc_size': {
                                'type': 'string',
                                'required': True,
                                'allowed': ['small', 'large', 'xlarge']
                            },
                            'pc_vip': {
                                'type': 'string',
                                'required': False,
                                'validator': validate_ip
                            },
                            'ip_list': {
                                'type': 'list',
                                'required': True,
                                'schema': {'validator': validate_ip}
                            },
                            'ntp_server_list': {
                                'type': 'list',
                                'required': False
                            },
                            'dns_server_ip_list': {
                                'type': 'list',
                                'required': False,
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
                }
            }
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
            'pc_credential': CREDENTIAL_SCHEMA,
            **OVA_UPLOAD_SCHEMA,
            **PC_IMAGE_UPLOAD_SCHEMA,
            'ncm': DEPLOY_OVA_AS_VM_SCHEMA,
            **DEPLOY_PC_CONFIG_SCHEMA
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
                        'pc_credential': CREDENTIAL_SCHEMA,
                        **EULA_SCHEMA,
                        **PULSE_SCHEMA,
                        'enable_fc': {'type': 'boolean'},
                        'generate_fc_api_key': {'type': 'boolean'},
                        'fc_alias_key_name': {'type': 'string'},
                        'clusters': {
                            'type': 'dict',
                            'keyschema': {'type': 'string', 'validator': validate_ip},
                            'valueschema': {
                                'type': 'dict',
                                'schema': {
                                    'pe_credential': CREDENTIAL_SCHEMA,
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

CVMF_UPDATE_SCHEMA = {
    'cvms': {
        'type': 'dict',
        'required': True,
        'keyschema': {'type': 'string', 'validator': validate_ip},
        'valueschema': {
            'type': 'dict',
            'schema': {
                'cvm_credential': {'type': 'string', 'validator': contains_whitespace, 'required': True},
                'foundation_build_url': {'type': 'string', 'required': True, 'validator': contains_whitespace, },
                'foundation_version': {'type': 'string', 'required': True, 'validator': contains_whitespace, },
                'downgrade': {'type': 'boolean', 'required': False},
                'nameserver': {'type': 'string', 'required': False}
            }
        },
    }
}

NDB_COMPUTE_PROFILES = {
    "compute_profiles": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "name": {
                    "type": "string",
                    "required": True
                },
                "num_vcpus": {
                    "type": "integer",
                    "required": True
                },
                "memory_gib": {
                    "type": "integer",
                    "required": True
                },
                "num_cores_per_vcpu": {
                    "type": "integer",
                    "required": True
                }
            }
        }
    }
}

NDB_SCHEMA = {
    "ndb": {
        "type": "dict",
        "schema": {
            "ndb_credential": CREDENTIAL_SCHEMA,
            **PULSE_SCHEMA,
            **NDB_COMPUTE_PROFILES,
            "deployment_cluster": {
                "type": "dict",
                "required": True,
                "schema": {
                    "cluster_ip": {
                        "required": True,
                        "type": "string",
                        "validator": validate_ip
                    },
                    "pe_credential": CREDENTIAL_SCHEMA,
                    "ndb_vm_name": {
                        "type": "string",
                        "required": True
                    },
                    **PE_IMAGE_UPLOAD_SCHEMA,
                    "ndb_vm_config": {
                        "type": "dict",
                        "schema": {
                            "hypervisor_type": {
                                "type": "string",
                                "required": True,
                                "allowed": ["ESXI", "AHV"]
                            },
                            "timezone": {
                                "type": "string",
                                "required": True
                            },
                            "memory_mb": {
                                "type": "integer",
                                "required": True
                            },
                            "num_vcpus": {
                                "type": "integer",
                                "required": True
                            },
                            "num_cores_per_vcpu": {
                                "type": "integer",
                                "required": True
                            },
                            "boot_type": {
                                "type": "string",
                                "required": True,
                                "allowed": ["LEGACY", "SECURE_BOOT"]
                            },
                            "boot_disk": {
                                "type": "dict",
                                "required": True,
                                "schema": {
                                    "is_cdrom": {
                                        "type": "boolean"
                                    },
                                    "is_empty": {
                                        "type": "boolean"
                                    },
                                    "device_bus": {
                                        "type": "string",
                                        "allowed": ["IDE", "SATA", "SCSI"],
                                        "required": True
                                    },
                                    "vm_disk_clone": {
                                        "type": "dict",
                                        "schema": {
                                            "image": {
                                                "type": "string",
                                                "required": True
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "register_clusters": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "cluster_ip": {
                            "required": True,
                            "type": "string",
                            "validator": validate_ip
                        },
                        "pe_credential": CREDENTIAL_SCHEMA,
                        "initial_cluster": {
                            "type": "boolean"
                        },
                        "name": {
                            "type": "string",
                            "required": True
                        },
                        "storage_container": {
                            "type": "string",
                            "required": True
                        },
                        "dhcp_networks": {
                            "type": "list",
                            "schema": {
                                "type": "string"
                            }
                        },
                        "static_networks": {
                            "type": "dict",
                            "keyschema": {"type": "string"},
                            "valueschema": {
                                "type": "dict",
                                "schema": {
                                    "gateway": {
                                        "type": "string",
                                        "validator": validate_ip,
                                        "required": True,
                                    },
                                    "netmask": {
                                        "type": "string",
                                        "validator": validate_netmask,
                                        "required": True,
                                    },
                                    "ip_pools": {
                                        "type": "list",
                                        "schema": {
                                            "type": "list",
                                            "schema": {
                                                "type": "string"
                                            }
                                        }
                                    }
                                }
                            }

                        },
                        "agent_vm_vlan": {
                            "type": "string",
                            "dependencies": ["static_networks"]
                        },
                        "agent_vm_ip": {
                            "type": "string",
                            "validator": validate_ip,
                        },
                        "default_network_profile_vlan": {
                            "type": "string",
                            "dependencies": ["static_networks"]
                        },
                        "network_profiles": {
                            "type": "list",
                            "schema": {
                                "type": "dict",
                                "schema": {
                                    "name": {
                                        "type": "string",
                                        "required": True
                                    },
                                    "vlan": {
                                        "type": "string",
                                        "required": True
                                    },
                                    "engine": {
                                        "type": "string",
                                        "required": True,
                                        "allowed": ["postgres_database", "mysql_database", "oracle_database",
                                                    "sqlserver_database", "mariadb_database", "mongodb_database"]
                                    },
                                    "topology": {
                                        "type": "string",
                                        "required": True,
                                        "allowed": ["single", "cluster", "ALL", "instance"]
                                    },
                                    "enable_ip_address_selection": {
                                        "type": "boolean"
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
