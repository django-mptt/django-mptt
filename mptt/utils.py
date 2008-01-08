"""
Utilities for working with lists of ``Model`` instances which represent
trees.
"""
import itertools

from django.db import connection

__all__ = ['previous_current_next', 'tree_item_iterator', 'drilldown_for_node']

qn = connection.ops.quote_name

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
    for previous, current, next in previous_current_next(items):
        new_level = previous is None and True or previous.level < current.level
        if next is None:
            closed_levels = range(current.level, -1, -1)
        else:
            closed_levels = range(current.level, next.level, -1)
        yield current, {'new_level': new_level, 'closed_levels': closed_levels}

count_subquery = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s = %(mpttry_table)s.%(mptt_pk)s
)"""

cumulative_count_subquery = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s IN
    (
        SELECT m2.%(mptt_pk)s
        FROM %(mptt_table)s m2
        WHERE m2.%(tree_id)s = %(mptt_table)s.%(tree_id)s
          AND m2.%(left)s BETWEEN %(mptt_table)s.%(left)s
                              AND %(mptt_table)s.%(right)s
    )
)"""

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
        query_formatting_dict = {
            'rel_table': qn(rel_cls._meta.db_table),
            'mptt_fk': qn(rel_cls._meta.get_field(rel_field).column),
            'mptt_table': qn(node._meta.db_table),
            'mptt_pk': qn(node._meta.pk.column),
        }
        if cumulative:
            tree = node._tree_manager
            query_formatting_dict.update({
                'tree_id': qn(node._meta.get_field(tree.tree_id_attr).column),
                'left': qn(node._meta.get_field(tree.left_attr).column),
                'right': qn(node._meta.get_field(tree.right_attr).column),
            })
            subquery = cumulative_count_subquery % query_formatting_dict
        else:
            subquery = count_subquery % query_formatting_dict
        children = children.extra(select={count_attr: subquery})
    return itertools.chain(node.get_ancestors(), [node], children)
