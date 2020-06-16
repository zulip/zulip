from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from zerver.decorator import add_google_analytics


def get_isolated_page(request: HttpRequest) -> bool:
    '''Accept a GET param `?nav=no` to render an isolated, navless page.'''
    return request.GET.get('nav') == 'no'

@add_google_analytics
def terms_view(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request, 'zerver/terms.html',
        context={'isolated_page': get_isolated_page(request)},
    )

@add_google_analytics
def privacy_view(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(
        request, 'zerver/privacy.html',
        context={'isolated_page': get_isolated_page(request)},
    )
