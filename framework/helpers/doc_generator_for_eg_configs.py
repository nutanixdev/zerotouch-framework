import yaml

from framework.helpers.schema import *
example_config_directory_location = "config/example-configs"

schema_example_config_map = {
    f"{example_config_directory_location}/address_groups_pc.yml": [ADDRESS_GROUP_CREATE_SCHEMA, ADDRESS_GROUP_DELETE_SCHEMA],
    f"{example_config_directory_location}/authentication_pc.yml": [AD_CREATE_SCHEMA, AD_DELETE_SCHEMA],
    f"{example_config_directory_location}/authentication_pe.yml": [AD_CREATE_SCHEMA, AD_DELETE_SCHEMA],
    f"{example_config_directory_location}/category_pc.yml": [CATEGORIES_CREATE_SCHEMA, CATEGORIES_DELETE_SCHEMA],
    f"{example_config_directory_location}/objectstore_buckets.yml": [OBJECTS_CREATE_SCHEMA, OBJECTS_DELETE_SCHEMA],
    f"{example_config_directory_location}/protection_policy.yml": [PROTECTION_RULES_CREATE_SCHEMA, PROTECTION_RULES_DELETE_SCHEMA],
    f"{example_config_directory_location}/recovery_plan.yml": [RECOVERY_PLAN_CREATE_SCHEMA, RECOVERY_PLAN_DELETE_SCHEMA],
    f"{example_config_directory_location}/remote_az.yml": [REMOTE_AZS_CONNECT_SCHEMA, REMOTE_AZS_DISCONNECT_SCHEMA],
    f"{example_config_directory_location}/security_policy.yml": [SECURITY_POLICIES_CREATE_SCHEMA, SECURITY_POLICIES_DELETE_SCHEMA],
    f"{example_config_directory_location}/service_groups.yml": [SERVICE_GROUP_CREATE_SCHEMA, SERVICE_GROUP_DELETE_SCHEMA],
    f"{example_config_directory_location}/storage_container_pe.yml": [CONTAINERS_CREATE_SCHEMA, CONTAINERS_DELETE_SCHEMA],
    f"{example_config_directory_location}/subnets_pe.yml": [NETWORKS_CREATE_SCHEMA, NETWORKS_DELETE_SCHEMA],
    f"{example_config_directory_location}/subnets_pc.yml": [NETWORKS_CREATE_SCHEMA, NETWORKS_DELETE_SCHEMA],
    f"{example_config_directory_location}/pc_image.yml": [IMAGE_UPLOAD_SCHEMA, IMAGE_DELETE_SCHEMA],
    f"{example_config_directory_location}/pc_ova.yml": [OVA_UPLOAD_SCHEMA, OVA_DELETE_SCHEMA]
}

def remove_validators_from_schema(json_schema):
    if isinstance(json_schema, dict):
        schema = {}
        for key, value in json_schema.items():
            if key != "validator":
                schema[key] = remove_validators_from_schema(value)
        return schema
    elif isinstance(json_schema, list):
        return [remove_validators_from_schema(item) for item in json_schema]
    else:
        return json_schema
    
def generate_commented_yaml_from_schema(json_schema):
    json_without_validators = remove_validators_from_schema(json_schema)
    yaml_data = yaml.dump(json_without_validators, sort_keys=False)
    commented_yaml_str = "\n".join(f"# {line}" for line in yaml_data.split("\n"))
    return str(commented_yaml_str)

def delete_previous_comments(filename):
    # Read the file into memory
    start_string = ('#'*40 + " SCHEMA DOCUMENTATION "+ '#'*40)
    with open(filename, 'r') as file:
        lines = file.readlines()

    # Find the index of the line containing the start string
    for i, line in enumerate(lines):
        if start_string in line:
            break
    else:
        # If the start string is not found, return
        return

    # Truncate the file from the line containing the start string onwards
    with open(filename, 'w') as file:
        file.writelines(lines[:(i-2)])

    
if __name__ == "__main__":
    
    for file_path,schema in schema_example_config_map.items():
        delete_previous_comments(file_path)

        to_be_appended_text = ("\n\n"+"#"*40 + " SCHEMA DOCUMENTATION "+ "#"*40)
        if isinstance(schema,list):
            headers = iter(["CREATE", "DELETE", "CLUSTERS"])
            for json_schema in schema:
                to_be_appended_text += ("\n")
                to_be_appended_text += f"### \t\t\t---{next(headers)} SCHEMA --- \t\t\t ###\n\n"
                to_be_appended_text += generate_commented_yaml_from_schema(json_schema)
                to_be_appended_text += ("\n\n")

        else:
            to_be_appended_text += generate_commented_yaml_from_schema(schema)
        to_be_appended_text += ("#"*100 + "\n")
        with open(file_path, 'a') as file:
            file.write(to_be_appended_text)
