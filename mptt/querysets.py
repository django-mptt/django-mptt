from django.db import models

from mptt import utils


class TreeQuerySet(models.query.QuerySet):
    def get_descendants(self, *args, **kwargs):
        return self.model.objects.get_queryset_descendants(self, *args, **kwargs)
    get_descendants.queryset_only = True

    def get_ancestors(self, *args, **kwargs):
        return self.model.objects.get_queryset_ancestors(self, *args, **kwargs)
    get_ancestors.queryset_only = True

    def get_cached_trees(self):
        """
        Assuming a queryset of model objects in MPTT left (depth-first) order,
        caches the children on each node, as well as the parent of each child
        node, allowing up and down traversal through the tree without the need
        for further queries. This makes it possible to have a recursively
        included template without worrying about database queries.

        Returns a list of top-level nodes. If a single tree was provided in its
        entirety, the list will of course consist of just the tree's root node.
        """
        return utils.get_cached_trees(self)
