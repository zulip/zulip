from collections import OrderedDict
from django.views.generic import TemplateView

from zerver.lib.integrations import INTEGRATIONS

class IntegrationView(TemplateView):
    template_name = 'zerver/integrations.html'

    def get_context_data(self, **kwargs):
        context = super(IntegrationView, self).get_context_data(**kwargs)
        alphabetical_sorted_integration = OrderedDict(sorted(INTEGRATIONS.items()))
        context['integrations_dict'] = alphabetical_sorted_integration
        return context
