"""
Custom managers for working with trees of objects.
"""
from django.db import models

__all__ = ['TreeManager']

class TreeManager(models.Manager):
    """
    A manager for working with trees of objects.
    """
    def __init__(self, parent_attr, left_attr, right_attr, tree_id_attr,
                 level_attr):
        """
        Tree related attributes for the model being managed are held as
        attributes of this manager for later use.
        """
        super(TreeManager, self).__init__()
        self.parent_attr = parent_attr
        self.left_attr = left_attr
        self.right_attr = right_attr
        self.tree_id_attr = tree_id_attr
        self.level_attr = level_attr

    def get_query_set(self):
        """
        Returns a ``QuerySet`` which contains all tree items, ordered in
        such a way that that trees appear in the order they were created
        and items appear in depth-first order within their tree.
        """
        return super(TreeManager, self).get_query_set().order_by(
            self.tree_id_attr, self.left_attr)
