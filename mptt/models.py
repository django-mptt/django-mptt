"""
New instance methods for Django models which are set up for Modified
Preorder Tree Traversal.
"""

from django.db.models import F

def get_ancestors(self, ascending=False):
    """
    Creates a ``QuerySet`` containing the ancestors of this model
    instance.

    This defaults to being in descending order (root ancestor first,
    immediate parent last); passing ``True`` for the ``ascending``
    argument will reverse the ordering (immediate parent first, root
    ancestor last).
    """
    if self.is_root_node():
        return self._tree_manager.none()

    opts = self._meta
    
    order_by = opts.left_attr
    if ascending:
        order_by = '-%s' % order_by
    
    qs = self._tree_manager._mptt_filter(
        left__lt=getattr(self, opts.left_attr),
        right__gt=getattr(self, opts.right_attr),
        tree_id=getattr(self, opts.tree_id_attr),
    )
    return qs.order_by(order_by)

def get_children(self):
    """
    Returns a ``QuerySet`` containing the immediate children of this
    model instance, in tree order.

    The benefit of using this method over the reverse relation
    provided by the ORM to the instance's children is that a
    database query can be avoided in the case where the instance is
    a leaf node (it has no children).
    
    If called from a template where the tree has been walked by the
    ``cache_tree_children`` filter, no database query is required.
    """
    
    if hasattr(self, '_cached_children'):
        return self._cached_children
    else:
        if self.is_leaf_node():
            return self._tree_manager.none()

        return self._tree_manager._mptt_filter(parent=self)

def get_descendants(self, include_self=False):
    """
    Creates a ``QuerySet`` containing descendants of this model
    instance, in tree order.

    If ``include_self`` is ``True``, the ``QuerySet`` will also
    include this model instance.
    """
    if not include_self and self.is_leaf_node():
        return self._tree_manager.none()

    opts = self._meta
    left = getattr(self, opts.left_attr)
    right = getattr(self, opts.right_attr)
    
    if not include_self:
        left += 1
        right -= 1
    
    return self._tree_manager._mptt_filter(
        tree_id=getattr(self, opts.tree_id_attr),
        left__gte=left,
        left__lte=right
    )

def get_descendant_count(self):
    """
    Returns the number of descendants this model instance has.
    """
    return (getattr(self, self._meta.right_attr) -
            getattr(self, self._meta.left_attr) - 1) / 2

def get_leafnodes(self, include_self=False):
    """
    Creates a ``QuerySet`` containing leafnodes of this model
    instance, in tree order.

    If ``include_self`` is ``True``, the ``QuerySet`` will also
    include this model instance (if it is a leaf node)
    """
    descendants = get_descendants(self, include_self=include_self)
    
    return self._tree_manager._mptt_filter(descendants,
        left=F(self._meta.right_attr)-1
    )

def get_next_sibling(self, **filters):
    """
    Returns this model instance's next sibling in the tree, or
    ``None`` if it doesn't have a next sibling.
    """
    opts = self._meta
    qs = self._tree_manager.filter(**filters)
    if self.is_root_node():
        qs = self._tree_manager._mptt_filter(qs,
            parent__isnull=True,
            tree_id__gt=getattr(self, opts.tree_id_attr),
        )
    else:
        qs = self._tree_manager._mptt_filter(qs,
            parent__id=getattr(self, '%s_id' % opts.parent_attr),
            left__gt=getattr(self, opts.right_attr),
        )
    
    siblings = qs[:1]
    return siblings[0] if siblings else None

def get_previous_sibling(self, **filters):
    """
    Returns this model instance's previous sibling in the tree, or
    ``None`` if it doesn't have a previous sibling.
    """
    opts = self._meta
    qs = self._tree_manager.filter(**filters)
    if self.is_root_node():
        qs = self._tree_manager._mptt_filter(qs,
            parent__isnull=True,
            tree_id__lt=getattr(self, opts.tree_id_attr),
        )
        qs = qs.order_by('-%s' % opts.tree_id_attr)
    else:
        qs = self._tree_manager._mptt_filter(qs,
            parent__id=getattr(self, '%s_id' % opts.parent_attr),
            right__lt=getattr(self, opts.left_attr),
        )
        qs = qs.order_by('-%s' % opts.right_attr)

    siblings = qs[:1]
    return siblings[0] if siblings else None

def get_root(self):
    """
    Returns the root node of this model instance's tree.
    """
    if self.is_root_node():
        return self
    
    return self._tree_manager._mptt_filter(
        tree_id=getattr(self, self._meta.tree_id_attr),
        parent__isnull=True
    ).get()

def get_siblings(self, include_self=False):
    """
    Creates a ``QuerySet`` containing siblings of this model
    instance. Root nodes are considered to be siblings of other root
    nodes.

    If ``include_self`` is ``True``, the ``QuerySet`` will also
    include this model instance.
    """
    if self.is_root_node():
        queryset = self._tree_manager._mptt_filter(parent__isnull=True)
    else:
        queryset = self._tree_manager._mptt_filter(parent__id=getattr(self, '%s_id' % self._meta.parent_attr))
    if not include_self:
        queryset = queryset.exclude(pk=self.pk)
    return queryset

def get_level(self):
    """
    Returns the level of this node (distance from root)
    """
    return getattr(self, self._meta.level_attr)

def insert_at(self, target, position='first-child', save=False):
    """
    Convenience method for calling ``TreeManager.insert_node`` with this
    model instance.
    """
    self._tree_manager.insert_node(self, target, position, save)

def is_child_node(self):
    """
    Returns ``True`` if this model instance is a child node, ``False``
    otherwise.
    """
    return not self.is_root_node()

def is_leaf_node(self):
    """
    Returns ``True`` if this model instance is a leaf node (it has no
    children), ``False`` otherwise.
    """
    return not self.get_descendant_count()

def is_root_node(self):
    """
    Returns ``True`` if this model instance is a root node,
    ``False`` otherwise.
    """
    return getattr(self, '%s_id' % self._meta.parent_attr) is None

def move_to(self, target, position='first-child'):
    """
    Convenience method for calling ``TreeManager.move_node`` with this
    model instance.
    """
    self._tree_manager.move_node(self, target, position)
