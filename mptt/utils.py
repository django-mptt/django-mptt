"""
Utilities for working with lists of ``Model`` instances which represent
trees.
"""
import itertools

from mptt import queries

__all__ = ['previous_current_next', 'tree_item_iterator', 'drilldown_for_node']

def previous_current_next(items):
    """
    From http://www.wordaligned.org/articles/zippy-triples-served-with-python

    Creates an iterator which returns (previous, current, next) triples,
    with ``None`` filling in when there is no previous or next
    available.
    """
    extend = itertools.chain([None], items, [None])
    previous, current, next = itertools.tee(extend, 3)
    try:
        current.next()
        next.next()
        next.next()
    except StopIteration:
        pass
    return itertools.izip(previous, current, next)

def tree_item_iterator(items):
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
    """
    opts = None
    for previous, current, next in previous_current_next(items):
        if opts is None:
            opts = current._meta
        current_level = getattr(current, opts.level_attr)
        new_level = (previous is None and True
                     or getattr(previous, opts.level_attr) < current_level)
        if next is None:
            closed_levels = range(current_level, -1, -1)
        else:
            closed_levels = range(current_level,
                                  getattr(next, opts.level_attr), -1)
        yield current, {'new_level': new_level, 'closed_levels': closed_levels}

def drilldown_tree_for_node(node, rel_cls=None, rel_field=None, count_attr=None,
                            cumulative=False):
    """
    Creates a drilldown tree for the given node. A drilldown tree
    consists of a node's ancestors, itself and its immediate children,
    all in tree order.

    Optional arguments may be given to specify a ``Model`` class which
    is related to the node's class, for the purpose of adding related
    item counts to the node's children:

    ``rel_cls``
       A ``Model`` class which has a relation to the node's class.

    ``rel_field``
       The name of the field in ``rel_cls`` which holds the relation
       to the node's class.

    ``count_attr``
       The name of an attribute which should be added to each item in
       the drilldown tree, containing a count of how many instances
       of ``rel_cls`` are related to it through ``rel_field``.

    ``cumulative``
       If ``True``, the count will be for items related to the child
       node and all of its descendants.
    """
    children = node.get_children()
    if rel_cls is not None and rel_field is not None and count_attr is not None:
        subquery_func = (cumulative and queries.create_cumulative_count_subquery
                                     or queries.create_count_subquery)
        children = children.extra(select={
            count_attr: subquery_func(node, rel_cls, rel_field),
        })
    return itertools.chain(node.get_ancestors(), [node], children)
