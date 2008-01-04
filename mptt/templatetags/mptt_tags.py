"""
Template tags for working with lists of ``Model`` instances which
represent trees.
"""
from django import template
from django.db.models import get_model

from mptt.utils import tree_item_iterator

register = template.Library()

class FullTreeForModelNode(template.Node):
    def __init__(self, model, context_var):
        self.model = model
        self.context_var = context_var

    def render(self, context):
        cls = get_model(*self.model.split('.'))
        context[self.context_var] = cls._tree_manager.all()
        return ''

def do_full_tree_for_model(parser, token):
    """
    Populates a template variable with a ``QuerySet`` containing the
    full tree for a given model.

    Usage::

        {% full_tree_for_model [model] as [varname] %}

    The model is specified in ``[appname].[modelname]`` format.

    Example::

        {% full_tree_for_model tests.Genre as genres %}

    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise template.TemplateSyntaxError('%s tag requires three arguments' % bits[0])
    if bits[2] != 'as':
        raise template.TemplateSyntaxError("second argument to %s tag must be 'as'" % bits[0])
    return FullTreeForModelNode(bits[1], bits[3])

def tree_info(items):
    """
    Given a list of tree items, produces doubles of a tree item and a
    ``dict`` containing information about the tree structure around the
    item, with the following contents:

       new_level
          ``True`` if the current item is the start of a new level in
          the tree, ``False`` otherwise.

       closed_levels
          A list of levels which end after the current item. This will
          be an empty list if the next item is at the same level as the
          current item.

    Using this filter with unpacking in a ``{% for %}`` tag, you should
    have enough information about the tree structure to create a
    hierarchical representation of the tree.

    Example::

       {% for genre,tree in genres|tree_info %}
       {% if tree.new_level %}<ul><li>{% else %}</li><li>{% endif %}
       {{ genre.name }}
       {% for level in tree.closed_levels %}</li></ul>{% endfor %}
       {% endfor %}

    """
    return tree_item_iterator(items)

register.tag('full_tree_for_model', do_full_tree_for_model)
register.filter('tree_info', tree_info)
