from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity


class IdentityProvider(PcEntity):
    kind = "identity_provider"
    version = "3.1"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/identity_providers"
        super(IdentityProvider, self).__init__(session=session)

    # The create_idp method creates a new identity provider with the given parameters.
    def create_idp(self, name: str, idp_metadata: str = None, idp_properties: dict = None, **kwargs):
        """
        Create Identity Provider
        Args:
            name(str): Name of the Identity Provider
            idp_metadata(str): IDP Metadata
            idp_properties(dict): IDP Config

        Returns:
          The json response returned by API.
        """
        payload = self.get_payload(name, idp_metadata, idp_properties, **kwargs)
        return self.create(data=payload)

    def get_payload(self, name: str, idp_metadata: str = None, idp_properties: dict = None, **kwargs):
        """
        Generated payload to create an Identity Provider
        Args:
            name(str): Name of the Identity Provider
            idp_metadata(str): IDP Metadata
            idp_properties(dict): IDP Config

        Returns:
          payload
        """

        # The payload for the API request is created with the given parameters
        payload = {
            "spec": {
                "name": name,
            },
            "metadata": {"kind": self.kind},
            "api_version": self.version
        }

        if "username_attr" in kwargs:
            payload["spec"]["username_attr"] = kwargs["username_attr"]
        if "email_attr" in kwargs:
            payload["spec"]["email_attr"] = kwargs["email_attr"]
        if "groups_attr" in kwargs:
            payload["spec"]["groups_attr"] = kwargs["groups_attr"]
        if "groups_delim" in kwargs:
            payload["spec"]["groups_delim"] = kwargs["groups_delim"]

        # If idp_metadata is provided, it is added to the payload
        if idp_metadata is not None:
            payload["spec"]["resources"] = {
                "idp_metadata": idp_metadata
            }
        # If idp_properties is provided, it is added to the payload
        elif idp_properties is not None:
            payload["spec"]["resources"] = {
                "idp_properties": idp_properties
            }

        return payload
