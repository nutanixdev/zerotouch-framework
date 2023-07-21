import json5 as json
import re
import os
import cerberus
import yaml
from typing import List, Type, Iterable, Any
from distutils.file_util import copy_file
from scripts.python.script import Script
from functools import wraps
from .log_utils import get_logger
from .exception_utils import JsonError, YamlError

logger = get_logger(__name__)


def get_json_file_contents(file: str) -> dict:
    """
    Read contents of the json file, "file" and return the data
    """
    logger.info(f"Reading contents of the file: [{file}]")
    with open(file, 'r') as f:
        try:
            return json.load(f)
        except Exception as e:
            raise JsonError(str(e))


def get_yml_file_contents(file: str) -> dict:
    """
    Read contents of the json file, "file" and return the data
    """
    logger.info(f"Reading contents of the file: [{file}]")
    with open(file, 'r') as f:
        try:
            return yaml.safe_load(f)
        except Exception as e:
            raise YamlError(str(e))


def validate_ip(field, value, error):
    """
    Function to check if "value" is a valid ip or not, if not it'll raise error("field")
    Eg: validate_ip("cvm_ip", "1.1.1.1", Exception)
    """
    pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    if not pattern.match(value, ):
        error(field, '"{}" must be a valid IP address'.format(value))
        return False
    return True


def validate_subnet(field, value, error):
    """
    Function to check if "value" is a valid subnet or not, if not it'll raise error("field")
    Eg: validate_ip("cvm_ip", "1.1.1.0/24", Exception)
    """
    pattern = re.compile\
        (r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?/\d{1,2})')
    if not pattern.match(value, ):
        error(field, '"{}" must be a valid Subnet'.format(value))
        return False
    return True


def validate_ip_list(field, value, error):
    """
    Function to check if value has list of valid ip's or not, if not it'll raise error("field")
    Eg: validate_ip("cvm_ip", "1.1.1.1", Exception)
    """
    pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    for ip in value:
        if not pattern.match(ip, ):
            error(field, '"{}" must be a valid IP address'.format(ip))


def contains_whitespace(field, value, error):
    """
    Check if string has whitespace
    """
    if ' ' in value:
        error(field, f"Space is not allowed in {value}")


def validate_domain(field, value, error):
    """
    Function to validate the domain
    """
    pattern = re.compile(r'^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,6}$')
    if not isinstance(value, list):
        if not pattern.match(value, ):
            error(field, '"{}" must be a valid domain'.format(value))
    else:
        for domain in value:
            if not pattern.match(domain, ):
                error(field, '"{}" must be a valid domain'.format(domain))


def validate_schema(schema: dict, data: dict) -> bool:
    """
    Function used to validate json/ yaml schema
    data: input data to be verified
    schema: schema to be validated against
    """
    validated = False  # reflect whether the overall process succeeded
    validator = cerberus.Validator(schema, allow_unknown=True)

    if not validator.validate(data):
        logger.error(validator.errors)
    else:
        logger.info("Validated the schema successfully!")
        validated = True
    return validated


def create_new_directory(path: str):
    """
    Function to create a new directory "path"
    """
    logger.info(f"Creating directory [{path}] if it doesn't exist")
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        raise PermissionError
    except OSError as e:
        raise e


def delete_file_util(file_path: str):
    if os.path.exists(file_path):
        os.remove(file_path)


def copy_file_util(src_path: str, dst_path: str):
    """
    Function to copy a file from "src_path" to "dst_path"
    """
    try:
        copy_file(src_path, dst_path)
    except IOError as e:
        logger.info("IO error occurred while copying the file.")
        raise e
    except Exception as e:
        logger.error("An error occurred while copying the file.")
        raise e
    else:
        logger.info("File copied successfully!")


def run_script(scripts: List[Type[Script]], data: dict):
    """
    Provided list of "scripts", this function runs individual script using "run" and then runs "verify"
    """
    for script in scripts:
        logger.info(f"Calling the script '{script.__name__}'...")
        script_obj = script(data)
        try:
            script_obj.run()
        except Exception as e:
            logger.exception(e)
            continue


def intersection(first_obj, second_obj):
    """
    Function used to check if second_obj is present in first_obj
    """
    if isinstance(first_obj, dict):
        for key, value in first_obj.items():
            if key in second_obj and second_obj[key] == value:
                second_obj.pop(key)
            if isinstance(value, (dict, list)):
                intersection(value, second_obj)
        if not second_obj:
            return True
    elif isinstance(first_obj, list):
        for item in first_obj:
            intersection(item, second_obj)
    return False


def enforce_data_arg(func):
    """
    Function to enforce functions to just have 1 argument
    """

    @wraps(func)
    def wrapper(data):
        return func(data)

    return wrapper


def convert_to_secs(value: int, unit: str):
    """
    This routine converts given value to time interval into seconds as per unit
    """
    conversion_multiplier = {
        "MINUTE": 60,
        "HOUR": 3600,
        "DAY": 86400,
        "WEEK": 604800,
    }
    if unit not in conversion_multiplier:
        return None, "Invalid unit given for interval conversion to seconds"

    return value * conversion_multiplier[unit], None


def divide_chunks(iterable_to_divide: Iterable[Any], chunk_size: int):
    """Divide list into chunks of length n

    Args:
        iterable_to_divide (list): Iterable to divide into chunks of length chunk_size
        chunk_size (int): Length of the list chunks

    Yields:
        Chunks of list with length n
    """
    for i in range(0, len(iterable_to_divide), chunk_size):
        yield iterable_to_divide[i:i + chunk_size]
