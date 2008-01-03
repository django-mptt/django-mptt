"""
MPTT exceptions.
"""

class InvalidMove(Exception):
    """
    An invalid node move was attempted.

    For example, attempting to make any node a sibling of a root node.
    """
    pass

class InvalidTarget(Exception):
    """
    An invalid node was specified as a target for a node move.

    For example, passing a non-root node where a root node was expected.
    """
    pass
