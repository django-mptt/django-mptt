
# From djblets:
# http://github.com/djblets/djblets/blob/master/djblets/util/decorators.py
# Last updated from c903551cf6888784a80a453e072d6c31255d5558

from inspect import getargspec
from django import template
from django.template import TemplateSyntaxError, Variable

try:
    from djblets.util.decorators import basictag
except ImportError:
    def basictag(takes_context=False):
        """
        A decorator similar to Django's @register.simple_tag that optionally
        takes a context parameter. This condenses many tag implementations down
        to a few lines of code.

        Example:
            @register.tag
            @basictag(takes_context=True)
            def printuser(context):
                return context['user']
        """
        class BasicTagNode(template.Node):
            def __init__(self, take_context, tag_name, tag_func, args):
                self.takes_context = takes_context
                self.tag_name = tag_name
                self.tag_func = tag_func
                self.args = args

            def render(self, context):
                args = [Variable(var).resolve(context) for var in self.args]

                if self.takes_context:
                    return self.tag_func(context, *args)
                else:
                    return self.tag_func(*args)

        def basictag_func(tag_func):
            def _setup_tag(parser, token):
                bits = token.split_contents()
                tag_name = bits[0]
                del(bits[0])

                params, xx, xxx, defaults = getargspec(tag_func)
                max_args = len(params)

                if takes_context:
                    if params[0] == 'context':
                        max_args -= 1 # Ignore context
                    else:
                        raise TemplateSyntaxError, \
                            "Any tag function decorated with takes_context=True " \
                            "must have a first argument of 'context'"

                min_args = max_args - len(defaults or [])

                if not min_args <= len(bits) <= max_args:
                    if min_args == max_args:
                        raise TemplateSyntaxError, \
                            "%r tag takes %d arguments." % (tag_name, min_args)
                    else:
                        raise TemplateSyntaxError, \
                            "%r tag takes %d to %d arguments, got %d." % \
                            (tag_name, min_args, max_args, len(bits))

                return BasicTagNode(takes_context, tag_name, tag_func, bits)

            _setup_tag.__name__ = tag_func.__name__
            _setup_tag.__doc__ = tag_func.__doc__
            _setup_tag.__dict__.update(tag_func.__dict__)
            return _setup_tag

        return basictag_func
