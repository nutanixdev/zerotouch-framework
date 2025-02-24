from __future__ import annotations
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import json5
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import os
import cerberus
import yaml
import glob
from datetime import datetime
from netaddr import IPNetwork
from typing import List, Type, Iterable, Any, IO, Dict, Callable
from distutils.file_util import copy_file
from functools import wraps
from .log_utils import get_logger
from .exception_utils import JsonError, YamlError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from framework.scripts.python.script import Script

logger = get_logger(__name__)


class Loader(yaml.SafeLoader):
    """YAML Loader with `!include` constructor."""

    def __init__(self, stream: IO) -> None:
        """Initialise Loader."""

        try:
            self._root = os.path.split(stream.name)[0]
        except AttributeError:
            self._root = os.path.curdir

        super().__init__(stream)


def construct_include(loader: Loader, node: yaml.Node) -> Any:
    """Include file referenced at node."""

    filename = os.path.abspath(os.path.join(loader._root, loader.construct_scalar(node)))
    extension = os.path.splitext(filename)[1].lstrip('.')

    with open(filename, 'r') as f:
        if extension in ('yaml', 'yml'):
            return yaml.load(f, Loader)
        elif extension in ('json',):
            return json5.load(f)
        else:
            return ''.join(f.readlines())


yaml.add_constructor('!include', construct_include, Loader)


def get_json_file_contents(file: str) -> dict:
    """
    Read contents of the json file, "file" and return the data.

    Args:
        file (str): Path to the JSON file.

    Returns:
        dict: Contents of the JSON file.
    """
    logger.info(f"Reading contents of the file: [{file}]")
    with open(file, 'r') as f:
        try:
            return json5.load(f)
        except Exception as e:
            raise JsonError(str(e))


def get_yml_file_contents(file: str) -> dict:
    """
    Read contents of the YAML file, "file" and return the data.

    Args:
        file (str): Path to the YAML file.

    Returns:
        dict: Contents of the YAML file.
    """
    logger.info(f"Reading contents of the file: [{file}]")
    with open(file, 'r') as f:
        try:
            return yaml.load(f, Loader=Loader)
        except Exception as e:
            raise YamlError(str(e))


def validate_ip(field: str, value: str, error: Callable[[str, str], None]) -> bool:
    """
    Function to check if "value" is a valid IP or not, if not it'll raise error("field").

    Args:
        field (str): The field name.
        value (str): The value to validate.
        error (Callable[[str, str], None]): The error function to call if validation fails.

    Returns:
        bool: True if valid, False otherwise.
    """
    pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    if not pattern.match(value, ):
        error(field, f'"{value}" must be a valid IP address')
        return False
    return True


def validate_dsip(field: str, value: str, error: Callable[[str, str], None]) -> bool:
    """
    DSIP can either be get-ip-from-ipam/valid IP.

    Args:
        field (str): The field name.
        value (str): The value to validate.
        error (Callable[[str, str], None]): The error function to call if validation fails.

    Returns:
        bool: True if valid, False otherwise.
    """
    if value == "get-ip-from-ipam":
        return True
    return validate_ip(field, value, error)


def validate_subnet(field: str, value: str, error: Callable[[str, str], None]) -> bool:
    """
    Function to check if "value" is a valid subnet or not, if not it'll raise error("field").

    Args:
        field (str): The field name.
        value (str): The value to validate.
        error (Callable[[str, str], None]): The error function to call if validation fails.

    Returns:
        bool: True if valid, False otherwise.
    """
    pattern = re.compile(r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?/\d{1,2})')
    if not pattern.match(value):
        error(field, f'"{value}" must be a valid Subnet')
        return False
    return True


def validate_netmask(field: str, value: str, error: Callable[[str, str], None]) -> bool:
    """
    Function to check if "value" is a valid netmask or not, if not it'll raise error("field").

    Args:
        field (str): The field name.
        value (str): The value to validate.
        error (Callable[[str, str], None]): The error function to call if validation fails.

    Returns:
        bool: True if valid, False otherwise.
    """
    pattern = re.compile(r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    if not pattern.match(value):
        error(field, f'"{value}" must be a valid Netmask')
        return False
    return True


def validate_ip_list(field: str, value: List[str], error: Callable[[str, str], None]) -> None:
    """
    Function to check if value has list of valid IPs or not, if not it'll raise error("field").

    Args:
        field (str): The field name.
        value (List[str]): The list of IPs to validate.
        error (Callable[[str, str], None]): The error function to call if validation fails.
    """
    pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
    for ip in value:
        if not pattern.match(ip):
            error(field, f'"{ip}" must be a valid IP address')


def contains_whitespace(field: str, value: str, error: Callable[[str, str], None]) -> None:
    """
    Check if string has whitespace.

    Args:
        field (str): The field name.
        value (str): The value to check.
        error (Callable[[str, str], None]): The error function to call if validation fails.
    """
    if ' ' in value:
        error(field, f"Space is not allowed in {value}")


def validate_domain(field: str, value: str | List[str], error: Callable[[str, str], None]) -> None:
    """
    Function to validate the domain.

    Args:
        field (str): The field name.
        value (str | List[str]): The value or list of values to validate.
        error (Callable[[str, str], None]): The error function to call if validation fails.
    """
    pattern = re.compile(r'^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,6}$')
    if not isinstance(value, list):
        if not pattern.match(value):
            error(field, f'"{value}" must be a valid domain')
    else:
        for domain in value:
            if not pattern.match(domain):
                error(field, f'"{domain}" must be a valid domain')


def validate_schema(schema: dict, data: dict) -> bool:
    """
    Function used to validate json/yaml schema.

    Args:
        schema (dict): Schema to be validated against.
        data (dict): Input data to be verified.

    Returns:
        bool: True if valid, False otherwise.
    """
    validated = False  # reflect whether the overall process succeeded
    validator = cerberus.Validator(schema, allow_unknown=True)

    if not validator.validate(data):
        logger.error(validator.errors)
    else:
        logger.info("Validated the schema successfully!")
        validated = True
    return validated


def create_new_directory(path: str) -> None:
    """
    Function to create a new directory "path".

    Args:
        path (str): Path to the directory to create.
    """
    logger.info(f"Creating directory [{path}] if it doesn't exist")
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        raise PermissionError
    except OSError as e:
        raise e


def delete_file_util(file_path: str) -> None:
    """
    Function to delete a file if it exists.

    Args:
        file_path (str): Path to the file to delete.
    """
    if os.path.exists(file_path):
        os.remove(file_path)


def copy_file_util(src_path: str, dst_path: str) -> None:
    """
    Function to copy a file from "src_path" to "dst_path".

    Args:
        src_path (str): Source file path.
        dst_path (str): Destination file path.
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
        logger.info(f"File '{dst_path}' copied successfully!")


def run_script(scripts: List[Type[Script]], data: Dict) -> None:
    """
    Provided list of "scripts", this function runs individual script using "run" and then runs "verify".

    Args:
        scripts (List[Type[Script]]): List of script classes to run.
        data (Dict): Data to pass to the scripts.
    """
    for script in scripts:
        script_obj = script(data=data)
        try:
            script_obj.run()
        except Exception as e:
            logger.exception(e)
            continue


def intersection(first_obj: dict | list, second_obj: dict) -> bool:
    """
    Function used to check if second_obj is present in first_obj.

    Args:
        first_obj (dict | list): The first object to check.
        second_obj (dict): The second object to check.

    Returns:
        bool: True if second_obj is present in first_obj, False otherwise.
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


def enforce_data_arg(func: Callable) -> Callable:
    """
    Function to enforce functions to just have 1 argument.

    Args:
        func (Callable): The function to enforce.

    Returns:
        Callable: The wrapped function.
    """

    @wraps(func)
    def wrapper(data: dict, **kwargs) -> Any:
        return func(data, **kwargs)

    return wrapper


def convert_to_secs(value: int, unit: str) -> tuple[int | None, str | None]:
    """
    This routine converts given value to time interval into seconds as per unit.

    Args:
        value (int): The value to convert.
        unit (str): The unit of the value.

    Returns:
        tuple[int | None, str | None]: The converted value in seconds and an error message if any.
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


def divide_chunks(iterable_to_divide: Iterable[Any], chunk_size: int) -> Iterable[List[Any]]:
    """
    Divide list into chunks of length n.

    Args:
        iterable_to_divide (Iterable[Any]): Iterable to divide into chunks of length chunk_size.
        chunk_size (int): Length of the list chunks.

    Yields:
        Iterable[List[Any]]: Chunks of list with length n.
    """
    for i in range(0, len(iterable_to_divide), chunk_size):
        yield iterable_to_divide[i:i + chunk_size]


def create_log_dir_push_logs(dir_to_create: str, data: Dict) -> None:
    """
    Create log directory and push logs.

    Args:
        dir_to_create (str): Directory to create.
        data (Dict): Data containing project root and input files.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H_%M_%S")

    # as we are using mkdir -p, this will create the branch directory, along with logs directory as well
    logs_directory = os.path.join(dir_to_create, "logs")
    create_new_directory(logs_directory)

    # push logs to the branch
    source = data['project_root']
    log_files = glob.glob(os.path.join(source, "*.log"))
    html_files = glob.glob(os.path.join(source, "*.html"))

    for log_file in log_files:
        _, log_file_name = os.path.split(log_file)
        destination = os.path.join(logs_directory, f"{timestamp}_{log_file_name}")
        try:
            copy_file_util(log_file, destination)
        except Exception as e:
            raise Exception(e).with_traceback(e.__traceback__)
        finally:
            delete_file_util(log_file)

    for html_file in html_files:
        _, html_file_name = os.path.split(html_file)
        destination = os.path.join(logs_directory, f"{timestamp}_{html_file_name}")
        try:
            copy_file_util(html_file, destination)
        except Exception as e:
            raise Exception(e).with_traceback(e.__traceback__)
        finally:
            delete_file_util(html_file)

    config_directory = os.path.join(dir_to_create, "configs")
    create_new_directory(config_directory)

    # push input configs to the branch
    files = data["input_files"]

    for file in files:
        _, file_name = os.path.split(file)
        destination = os.path.join(config_directory, f"{timestamp}_{file_name}")
        try:
            if os.path.exists(file):
                copy_file_util(file, destination)
        except Exception as e:
            raise Exception(e).with_traceback(e.__traceback__)


def get_subnet_mask(subnet: str) -> str:
    """
    Get the subnet mask.

    Args:
        subnet (str): Subnet E.g 10.0.0.1/24.

    Returns:
        str: Return subnet mask Eg. 255.255.255.0.
    """
    ip_addr = IPNetwork(subnet)
    return str(ip_addr.netmask)


def send_mail_helper(subject: str, body: str, from_mail: str, to_mail: str, smtp_host: str,
                     attachment_path: str = "", port: int = 25) -> None:
    """
    Helper function to send an email.

    Args:
        subject (str): Subject of the email.
        body (str): Body of the email.
        from_mail (str): Sender's email address.
        to_mail (str): Recipient's email address.
        smtp_host (str): SMTP host.
        attachment_path (str, optional): Path to the attachment. Defaults to "".
        port (int, optional): SMTP port. Defaults to 25.
    """
    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_mail
    msg['To'] = to_mail

    html = body
    mime = MIMEText(html, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(mime)

    if attachment_path:
        part = MIMEBase('application', "octet-stream")
        with open(attachment_path, 'rb') as file:
            part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                        'attachment; filename={}'.format(Path(attachment_path).name))
        msg.attach(part)

    # Send the message via local SMTP server.
    s = smtplib.SMTP(host=smtp_host, port=port)
    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    # s.set_debuglevel(7)
    s.ehlo_or_helo_if_needed()
    # s.login("testuser", "w3lc0me")
    s.sendmail(from_mail, to_mail.split(","), msg.as_string())
    s.quit()
