from __future__ import absolute_import

import six
import sys

from typing import Any, Dict, List, Optional, Union, Text
if False:
    from mypy_extensions import NoReturn

import jinja2
from django.test.signals import template_rendered
from django.template.backends import jinja2 as django_jinja2
from django.template import TemplateDoesNotExist, TemplateSyntaxError, Context
from django.http import HttpRequest


class Jinja2(django_jinja2.Jinja2):
    """Context processors aware Jinja2 backend.

    The default Jinja2 backend in Django is not aware of context
    processors so we just derive from the default Jinja2 backend
    and add the functionality to pass the context processors to
    the `Template` object.
    """

    def __init__(self, params, *args, **kwargs):
        # type: (Dict[str, Any], *Any, **Any) -> None
        # We need to remove `context_processors` from `OPTIONS` because
        # `Environment` doesn't expect it
        context_processors = params['OPTIONS'].pop('context_processors', [])
        debug = params['OPTIONS'].pop('debug', False)
        super(Jinja2, self).__init__(params, *args, **kwargs)

        # We need to create these two properties after calling the __init__
        # of base class so that they are not overridden.
        self.context_processors = context_processors
        self.debug = debug

    def get_template(self, template_name):
        # type: (str) -> Template
        """
        The only we need to override this function is to use our own Template
        class. Jinja2 backend doesn't allow the usage of custom Template
        class.

        If in the future Django adds a method through which we can get a
        custom Template class, this method can be safely removed.
        """
        try:
            return Template(self.env.get_template(template_name), self)
        except jinja2.TemplateNotFound as exc:
            six.reraise(TemplateDoesNotExist, TemplateDoesNotExist(exc.args),
                        sys.exc_info()[2])
        except jinja2.TemplateSyntaxError as exc:
            six.reraise(TemplateSyntaxError, TemplateSyntaxError(exc.args),
                        sys.exc_info()[2])

    def from_string(self, template_code):
        # type: (str) -> Template
        """
        The only need to override this function is to use our own Template
        class. Jinja2 backend doesn't allow the usage of custom Template
        class.

        If in the future Django adds a method through which we can get a
        custom Template class, this method can be safely removed.
        """
        return Template(self.env.from_string(template_code), self)


class Template(django_jinja2.Template):
        """
        We need this class so that we can send the template_rendered signal,
        and to flatten the context if it is an instance of Context class.
        """
        def render(self, context=None, request=None):
            # type: (Optional[Union[Dict[str, Any], Context]], Optional[HttpRequest]) -> Text
            if context is None:
                context = {}

            if isinstance(context, Context):
                # Jinja2 expects a dictionary
                # This condition makes sure that `flatten` is called only when
                # `context` is an instance of `Context`.
                #
                # Note: If we don't ignore then mypy complains about missing
                # `flatten` attribute in some members of union.
                context = context.flatten()  # type: ignore

            result = super(Template, self).render(context=context,
                                                  request=request)

            if self.backend.debug:
                template_rendered.send(sender=self, template=self,
                                       context=context)

            return result
