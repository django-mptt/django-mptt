from django.db import models

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

        current_path = []
        top_nodes = []

        # If ``queryset`` is QuerySet-like, set ordering to depth-first
        if hasattr(self, 'order_by'):
            mptt_opts = self.model._mptt_meta
            tree_id_attr = mptt_opts.tree_id_attr
            left_attr = mptt_opts.left_attr
            if tuple(self.query.order_by) != (tree_id_attr, left_attr):
                warnings.warn(
                    "get_cached_trees() called on a queryset with the wrong " +
                    "ordering: %r.\nThis will cause an error in mptt 0.8." % (
                        self.query.order_by,),
                    UserWarning
                )
                self = self.order_by(tree_id_attr, left_attr)

        if self:
            # Get the model's parent-attribute name
            parent_attr = self[0]._mptt_meta.parent_attr
            root_level = None
            for obj in self:
                # Get the current mptt node level
                node_level = obj.get_level()

                if root_level is None:
                    # First iteration, so set the root level to the top node level
                    root_level = node_level

                if node_level < root_level:
                    # ``queryset`` was a list or other iterable (unable to order),
                    # and was provided in an order other than depth-first
                    raise ValueError(
                        _('Node %s not in depth-first order') % (type(self),)
                    )

                # Set up the attribute on the node that will store cached children,
                # which is used by ``MPTTModel.get_children``
                obj._cached_children = []

                # Remove nodes not in the current branch
                while len(current_path) > node_level - root_level:
                    current_path.pop(-1)

                if node_level == root_level:
                    # Add the root to the list of top nodes, which will be returned
                    top_nodes.append(obj)
                else:
                    # Cache the parent on the current node, and attach the current
                    # node to the parent's list of children
                    _parent = current_path[-1]
                    setattr(obj, parent_attr, _parent)
                    _parent._cached_children.append(obj)

                    if root_level == 0:
                        # get_ancestors() can use .parent.parent.parent...
                        setattr(obj, '_mptt_use_cached_ancestors', True)

                # Add the current node to end of the current path - the last node
                # in the current path is the parent for the next iteration, unless
                # the next iteration is higher up the tree (a new branch), in which
                # case the paths below it (e.g., this one) will be removed from the
                # current path during the next iteration
                current_path.append(obj)

        return top_nodes
    get_ancestors.queryset_only = True
