"""
SSH utility for CVM operations.

This module provides SSH connectivity and operations for CVMs,
similar to framework.scripts.python.helpers.cvm.ssh_cvm.SSHCvm
"""

import ipaddress
import shlex
import time

import paramiko

from ztf.utils.utils import get_logger

logger = get_logger(__name__)


class SSHCvm:
    """SSH client for CVM operations (foundation update, resolv.conf)."""

    def __init__(
        self,
        cvm_ip: str,
        username: str,
        password: str,
        port: int = 22,
        timeout: int = 30,
    ):
        self.cvm_ip = cvm_ip
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.client: paramiko.SSHClient | None = None
        self.logger = logger

    def _connect(self) -> bool:
        """Establish SSH connection to CVM."""
        try:
            if self.client is None:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
                self.client.connect(
                    hostname=self.cvm_ip,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                )
                self.logger.debug(f"SSH connection established to {self.cvm_ip}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.cvm_ip}: {e}")
            return False

    def _execute_command(self, command: str, timeout: int = 600) -> tuple[bool, str]:
        """
        Execute a command on the CVM via SSH.
        Reconnects per command to work around CVM SSH channel limits.
        """
        self.close()
        if not self._connect():
            return False, "Failed to establish SSH connection"
        if self.client is None:
            return False, "SSH connection not established"
        transport = self.client.get_transport()
        if not transport or not transport.is_active():
            return False, "SSH connection not active"
        try:
            full_command = f"source /etc/profile 2>/dev/null; {command}"
            stdin, stdout, stderr = self.client.exec_command(  # nosec B601
                full_command, timeout=timeout
            )
            output = stdout.read().decode("utf-8")
            error = stderr.read().decode("utf-8")
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                error_msg = (
                    error if error else f"Command failed with exit status {exit_status}"
                )
                self.logger.error(f"Command failed on {self.cvm_ip}: {error_msg}")
                return False, error_msg

            return True, output
        except Exception as e:
            self.logger.error(f"Error executing command on {self.cvm_ip}: {e}")
            return False, str(e)

    def update_resolv_conf(self, nameserver: str) -> tuple[bool, str]:
        """Update /etc/resolv.conf with the provided nameserver."""
        try:
            try:
                ipaddress.ip_address(nameserver)
            except ValueError:
                error_msg = f"Invalid nameserver IP address: {nameserver}"
                self.logger.error(f"{self.cvm_ip}: {error_msg}")
                return False, error_msg

            escaped = shlex.quote(nameserver)
            check_cmd = f"grep -q {escaped} /etc/resolv.conf"
            success, _ = self._execute_command(check_cmd)

            if success:
                self.logger.info(
                    f"{self.cvm_ip}: Nameserver {nameserver} already exists in resolv.conf"
                )
                return True, ""

            ns_line = shlex.quote(f"nameserver {nameserver}")
            update_cmd = f"printf '%s\\n' {ns_line} | sudo tee -a /etc/resolv.conf"
            success, output = self._execute_command(update_cmd)

            if success:
                self.logger.info(
                    f"{self.cvm_ip}: Successfully updated resolv.conf with nameserver {nameserver}"
                )
                return True, ""
            return False, output

        except Exception as e:
            error_msg = f"Failed to update resolv.conf: {e}"
            self.logger.error(f"{self.cvm_ip}: {error_msg}")
            return False, error_msg

    def update_cvm_foundation(
        self, foundation_url_path: str, downgrade: bool = False
    ) -> tuple[bool, str]:
        """
        Update CVM foundation using the provided foundation URL.

        Upgrade path:  ~/foundation/bin/foundation_upgrade -t <tarfile>
        Downgrade path: backup ~/foundation, rm, untar new, stop foundation, restart genesis
        """
        tar_file_name = foundation_url_path.split("/")[-1]
        home_tar = f"/home/nutanix/{tar_file_name}"
        safe_tar = shlex.quote(tar_file_name)
        safe_home_tar = shlex.quote(home_tar)
        safe_url = shlex.quote(foundation_url_path)

        try:
            download_cmd = f"cd /home/nutanix && wget -q -O {safe_tar} {safe_url}"
            self.logger.info(
                f"{self.cvm_ip}: Downloading foundation from {foundation_url_path[:80]}..."
            )
            success, output = self._execute_command(download_cmd)
            if not success:
                return False, f"Failed to download foundation: {output}"

            success, output = self._execute_command(
                f"test -f {safe_home_tar} && echo EXISTS"
            )
            if not success or "EXISTS" not in output:
                return False, f"Downloaded file {home_tar} does not exist"

            if not downgrade:
                upgrade_cmd = f"~/foundation/bin/foundation_upgrade -t {safe_tar}"
                self.logger.info(f"{self.cvm_ip}: Running foundation_upgrade (upgrade)")
                success, output = self._execute_command(upgrade_cmd)
                if (
                    not success
                    or "Successfully completed upgrading foundation" not in output
                ):
                    return False, f"foundation_upgrade failed: {output}"
            else:
                self.logger.info(
                    f"{self.cvm_ip}: Downgrading foundation (backup, replace, restart)"
                )
                steps = [
                    ("Backup foundation", "cp -rf ~/foundation ~/foundation_ztf_bkp"),
                    ("Remove foundation", "/bin/rm -rf ~/foundation"),
                    ("Untar new foundation", f"cd /home/nutanix && tar -xf {safe_tar}"),
                ]
                for desc, cmd in steps:
                    self.logger.info(f"{self.cvm_ip}: {desc}")
                    ok, out = self._execute_command(cmd)
                    if not ok:
                        self._execute_command(
                            "cp -rf ~/foundation_ztf_bkp ~/foundation"
                        )
                        return False, f"{desc} failed: {out}"

                ok, out = self._execute_command("test -d ~/foundation && echo EXISTS")
                if not ok or "EXISTS" not in out:
                    self._execute_command("cp -rf ~/foundation_ztf_bkp ~/foundation")
                    return False, "Foundation dir missing after untar; restored backup"

                self._execute_command("/bin/rm -rf ~/foundation_ztf_bkp")

            self.logger.info(
                f"{self.cvm_ip}: Stopping foundation and restarting genesis"
            )
            success, output = self._execute_command("genesis stop foundation")
            if not success:
                self.logger.error(f"{self.cvm_ip}: Failed to stop foundation: {output}")
                return False, f"Failed to stop foundation: {output}"

            time.sleep(5)
            success, output = self._execute_command("genesis restart")
            if not success:
                self.logger.error(f"{self.cvm_ip}: Failed to restart genesis: {output}")
                return False, f"Failed to restart genesis: {output}"

            self._execute_command(f"/bin/rm -f {safe_home_tar}")

            self.logger.info(f"{self.cvm_ip}: Successfully updated CVM foundation")
            return True, ""

        except Exception as e:
            error_msg = f"Failed to update CVM foundation: {e}"
            self.logger.error(f"{self.cvm_ip}: {error_msg}")
            return False, error_msg

    def enable_replication_ports(
        self, ports: list[int] | None = None
    ) -> tuple[bool, str]:
        """
        Open replication ports on all CVMs in the cluster.

        Tries ``allssh`` first to apply on every CVM at once; falls back to
        running ``modify_firewall`` directly on the connected CVM when
        ``allssh`` is unavailable. Uses the Nutanix ``modify_firewall``
        utility so the rule persists across reboots.

        Args:
            ports: Port numbers to open. Defaults to the standard
                replication ports (2020, 2030, 2036, 2073, 2090).

        Returns:
            Tuple of (success: bool, output_or_error: str).

        Raises:
            ValueError: If *ports* is not a list of integers in 1–65535.
        """
        ports = self._validate_replication_ports(ports)

        ports_str = ",".join(str(p) for p in ports)
        modify_fw_cmd = (
            f"sudo /usr/local/nutanix/cluster/bin/modify_firewall "
            f"-f -o open -i eth0 -p {ports_str} -a"
        )

        self.logger.info(f"{self.cvm_ip}: Opening replication ports {ports_str}")

        allssh_cmd = f"allssh '{modify_fw_cmd}'"
        success, output = self._execute_command(allssh_cmd)
        if success:
            self.logger.info(
                f"{self.cvm_ip}: Successfully opened replication ports on all CVMs via allssh"
            )
            return True, output

        if "command not found" in output:
            self.logger.info(
                f"{self.cvm_ip}: allssh not available, running modify_firewall directly"
            )
            success, output = self._execute_command(modify_fw_cmd)
            if not success:
                return False, output
            self.logger.info(
                f"{self.cvm_ip}: Successfully opened replication ports on this CVM"
            )
            return True, output

        return False, output

    @staticmethod
    def _validate_replication_ports(ports: list[int] | None) -> list[int]:
        """Return a list of TCP ports safe to interpolate into ``modify_firewall``.

        Args:
            ports: Port numbers, or ``None`` for the default replication set.

        Returns:
            Validated port numbers.

        Raises:
            ValueError: If any entry is not an integer in 1–65535.
        """
        if ports is None:
            return [2020, 2030, 2036, 2073, 2090]
        if isinstance(ports, (bool, str, bytes)):
            raise ValueError(
                f"ports must be a list of integers, got {type(ports).__name__}"
            )
        if isinstance(ports, int):
            ports = [ports]
        if not isinstance(ports, list | tuple) or not ports:
            raise ValueError("ports must be a non-empty list of integers")

        validated: list[int] = []
        for raw in ports:
            port: int
            if isinstance(raw, bool) or not isinstance(raw, int):
                if isinstance(raw, str) and raw.strip().isdigit():
                    port = int(raw)
                else:
                    raise ValueError(
                        f"Invalid replication port {raw!r}; "
                        "expected an integer in 1-65535"
                    )
            else:
                port = raw
            if port < 1 or port > 65535:
                raise ValueError(
                    f"Invalid replication port {port}; expected an integer in 1-65535"
                )
            validated.append(port)
        return validated

    def close(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.logger.debug(f"SSH connection closed for {self.cvm_ip}")

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
