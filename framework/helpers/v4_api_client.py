import ntnx_microseg_py_client
import ntnx_networking_py_client
import ntnx_prism_py_client

CLIENT_MAPPER = {
    'microseg': ntnx_microseg_py_client,
    'network': ntnx_networking_py_client,
    'prism': ntnx_prism_py_client
}

class ApiClientV4:
    def __init__(self, ip_address, port, user, pwd):
        self.ip_address = ip_address
        self.port = port
        self.user = user
        self.pwd = pwd
        self.cache = {}

    def get_api_client(self, client_type, max_retry_attempts=3, backoff_factor=3, verify_ssl=False):
        """
        Get the cached client or create a new one if not cached.

        Args:
            client_type (str): The type of client to create ('microseg', 'network', 'prism').
            max_retry_attempts (int, optional): The maximum number of retry attempts. Defaults to 3.
            backoff_factor (int, optional): The backoff factor for retries. Defaults to 3.
            verify_ssl (bool, optional): Whether to verify SSL certificates. Defaults to False.

        Returns:
            ApiClient: An instance of the requested API client.
        Args:
            client_type (str): The type of client to create.
            max_retry_attempts (int): The maximum number of retry attempts.
            backoff_factor (int): The backoff factor for retries.
            verify_ssl (bool): Whether to verify SSL certificates.

        Raises:
            ValueError: If the client_type is invalid.
        """
        if client_type in self.cache:
            return self.cache[client_type]

        new_client = self._create_api_client(client_type, max_retry_attempts, backoff_factor, verify_ssl)
        self.cache[client_type] = new_client
        return new_client

    def _create_api_client(self, client_type, max_retry_attempts, backoff_factor, verify_ssl):
        """Factory method to create a client based on the client_type.
        
        Raises:
            ValueError: If the client_type is invalid.
        """

        if client_type not in CLIENT_MAPPER:
            raise ValueError(f"Invalid client_type: {client_type}")

        config = CLIENT_MAPPER[client_type].Configuration()

        config.host = self.ip_address
        config.port = self.port
        config.max_retry_attempts = max_retry_attempts
        config.backoff_factor = backoff_factor
        config.username = self.user
        config.password = self.pwd
        config.verify_ssl = verify_ssl

        return CLIENT_MAPPER[client_type].ApiClient(configuration=config)
