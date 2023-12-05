from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity import PcEntity


class Blueprint(PcEntity):
    kind = 'blueprint'

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/blueprints"
        super(Blueprint, self).__init__(session=session)

    def list(self, **kwargs):
        filter_criteria = kwargs.pop('filters', 'state!=DELETED')
        return super(Blueprint, self).list(filter=filter_criteria, **kwargs)
