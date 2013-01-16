from django.views.debug import SafeExceptionReporterFilter

class HumbugExceptionReporterFilter(SafeExceptionReporterFilter):
    def get_post_parameters(self, request):
        filtered_post = SafeExceptionReporterFilter.get_post_parameters(self, request).copy()
        filtered_vars = ['content', 'secret', 'password', 'key', 'api_key', 'subject', 'stream',
                         'subscriptions', 'to']

        for var in filtered_vars:
            if var in filtered_post:
                filtered_post[var] = '**********'
        return filtered_post
