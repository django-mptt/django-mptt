"""
MPTT exceptions.
"""

class InvalidMove(Exception):
    """
    An invalid node move was attempted.

    For example, attempting to make any node a sibling of a root node.
    """
    pass
