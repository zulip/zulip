from __future__ import absolute_import

import sys
from typing import Any, Optional, Union
from six import text_type

import jinja2
from django.utils import six
from django.test.signals import template_rendered
from django.template.backends import jinja2 as django_jinja2
from django.template import TemplateDoesNotExist, TemplateSyntaxError, Context
from django.utils.module_loading import import_string
from django.template.backends.utils import csrf_input_lazy, csrf_token_lazy
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
        self.context_processors = params['OPTIONS'].pop('context_processors', [])
        self.debug = params['OPTIONS'].pop('debug', False)
        super(Jinja2, self).__init__(params, *args, **kwargs)

    def get_template(self, template_name):
        # type: (str) -> Template
        try:
            return Template(self.env.get_template(template_name),
                            self.context_processors,
                            self.debug)
        except jinja2.TemplateNotFound as exc:
            six.reraise(TemplateDoesNotExist, TemplateDoesNotExist(exc.args),
                        sys.exc_info()[2])
        except jinja2.TemplateSyntaxError as exc:
            six.reraise(TemplateSyntaxError, TemplateSyntaxError(exc.args),
                        sys.exc_info()[2])


class Template(django_jinja2.Template):
        """Context processors aware Template.

        This class upgrades the default `Template` to apply context
        processors to the context before passing it to the `render`
        function.
        """
        def __init__(self, template, context_processors, debug, *args, **kwargs):
            # type: (str, List[str], bool, *Any, **Any) -> None
            self.context_processors = context_processors
            self.debug = debug
            super(Template, self).__init__(template, *args, **kwargs)

        def render(self, context=None, request=None):
            # type: (Optional[Union[Dict[str, Any], Context]], Optional[HttpRequest]) -> text_type
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

            if request is not None:
                context['request'] = request
                context['csrf_input'] = csrf_input_lazy(request)
                context['csrf_token'] = csrf_token_lazy(request)

                for context_processor in self.context_processors:
                    cp = import_string(context_processor)
                    context.update(cp(request))

            if self.debug:
                template_rendered.send(sender=self, template=self,
                                       context=context)

            return self.template.render(context)
