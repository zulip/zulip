from django.views.debug import SafeExceptionReporterFilter

class HumbugExceptionReporterFilter(SafeExceptionReporterFilter):
    def get_post_parameters(self, request):
        filtered_post = SafeExceptionReporterFilter.get_post_parameters(self, request)
        if 'content' in filtered_post:
            filtered_post['content'] = '**********'
        if 'secret' in filtered_post:
            filtered_post['secret'] = '**********'
        return filtered_post
