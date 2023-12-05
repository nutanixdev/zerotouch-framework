import json
from typing import Dict
from calm.dsl.api import get_api_client
from calm.dsl.api.connection import REQUEST
from calm.dsl.api.setting import AccountsAPI
from calm.dsl.builtins import Account, AccountResources
from calm.dsl.cli.accounts import create_account, create_account_payload, get_account, verify_account
from calm.dsl.cli.utils import _get_nested_messages
from calm.dsl.constants import ACCOUNT, CACHE
from calm.dsl.store import Cache
from framework.helpers.log_utils import get_logger
from .script import Script

logger = get_logger(__name__)


# original create api in AccountsAPI has 'child_account==True' which is failing for calm 3.6.2, Hence re-writing
def proxy_create(self, account_name, account_payload, force_create):
    # check if account with the given name already exists
    params = {
        "filter": "name=={};state!=DELETED".format(account_name)
    }
    res, err = self.list(params=params)
    if err:
        return None, err

    response = res.json()

    entities = response.get("entitites", None)
    if entities:
        if len(entities) > 0:
            if not force_create:
                err_msg = "Account {} already exists. Use --force to first delete existing account before create."\
                    .format(account_name)
                err = {"error": err_msg, "code": -1}
                return None, err

            # --force option used in create. Delete existing account with same name.
            account_uuid = entities[0]["metadata"]["uuid"]
            _, err = self.delete(account_uuid)
            if err:
                return None, err

    return self.connection._call(
        self.CREATE,
        verify=False,
        request_json=account_payload,
        method=REQUEST.METHOD.POST,
        timeout=(5, 300),
    )


class CreateNcmAccount(Script):
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.account = self.data["ncm_account"]
        super(CreateNcmAccount, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            class AccountTemplate(Account):
                """DSL Account template"""
                # todo let's add other providers later
                # if self.account.get("type", ACCOUNT.TYPE.AHV) == ACCOUNT.TYPE.AHV:
                type = ACCOUNT.TYPE.AHV
                sync_interval = 900
                resources = AccountResources.Ntnx(
                    username=self.account.get("pc_username") or self.data.get("pc_username"),
                    password=self.account.get("pc_password") or self.data.get("pc_password"),
                    server=self.account.get("pc_ip") or self.data.get("pc_ip"),
                    port="9440"
                )

            client = get_api_client()
            # Create account takes name of the class as account name
            AccountTemplate.__name__ = self.account.get("name", "PC")
            account_payload = create_account_payload(AccountTemplate)

            if account_payload is None:
                self.exceptions.append("Account format invalid")
                return

            # client.account.proxy_create = proxy_create
            setattr(AccountsAPI, "proxy_create", proxy_create)
            res, err = client.account.proxy_create(
                self.account.get("name"),
                account_payload,
                force_create=False,
            )

            if err:
                self.exceptions.append(err["error"])
                return

            account = res.json()

            account_uuid = account["metadata"]["uuid"]
            account_name = account["metadata"]["name"]
            account_status = account.get("status", {})
            account_state = account_status.get("resources", {}).get("state", "DRAFT")
            account_type = account_status.get("resources", {}).get("type", "")
            logger.debug("Account {} has state: {}".format(account_name, account_state))

            if account_state == "DRAFT":
                msg_list = []
                _get_nested_messages("", account_status, msg_list)

                if not msg_list:
                    logger.error("Account {} created with errors.".format(account_name))
                    logger.debug(json.dumps(account_status))

                msgs = []
                for msg_dict in msg_list:
                    msg = ""
                    path = msg_dict.get("path", "")
                    if path:
                        msg = path + ": "
                    msgs.append(msg + msg_dict.get("message", ""))

                logger.error(
                    "Account {} created with {} error(s):".format(account_name, len(msg_list))
                )
                logger.info("\n".join(msgs))
                logger.info("Account went to {} state".format(account_state))
                return

            logger.info("Updating accounts cache ...")
            if account_type == ACCOUNT.TYPE.AHV:
                Cache.sync_table(
                    cache_type=[
                        CACHE.ENTITY.ACCOUNT,
                        CACHE.ENTITY.AHV_DISK_IMAGE,
                        CACHE.ENTITY.AHV_CLUSTER,
                        CACHE.ENTITY.AHV_VPC,
                        CACHE.ENTITY.AHV_SUBNET,
                    ]
                )
            else:
                # TODO Fix case for custom providers
                Cache.add_one(CACHE.ENTITY.ACCOUNT, account_uuid)
                logger.echo("[Done]")

            logger.info("Account {} created successfully.".format(account_name))

            logger.info(f"Verifying account {account_name}")

            verify_account(self.account.get("name"))
            return
        except Exception as e:
            self.exceptions.append(e)
        except SystemExit as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        try:
            if not self.account and not self.account.get("name"):
                return

            self.results["Create_Ncm_account"] = {}
            client = get_api_client()

            if get_account(client, self.account["name"]):
                self.results["Create_Ncm_account"][self.account["name"]] = "PASS"
            else:
                self.results["Create_Ncm_account"][self.account["name"]] = "FAIL"
        except SystemExit as e:
            self.exceptions.append(e)
