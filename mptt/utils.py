"""
Utilities for working with lists of ``Model`` instances which represent
trees.
"""
import itertools

__all__ = ['previous_current_next', 'tree_item_iterator']

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
