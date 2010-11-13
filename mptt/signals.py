"""
Signal receiving functions which handle Modified Preorder Tree Traversal
related logic when model instances are about to be saved or deleted.
"""
import operator

from django.db.models.query import Q

__all__ = ('post_init', 'pre_save', 'post_save')

def _update_mptt_cached_fields(instance):
    opts = instance._mptt_meta
    instance._mptt_cached_fields = {}
    field_names = [opts.parent_attr]
    if opts.order_insertion_by:
        field_names += opts.order_insertion_by
    for field_name in field_names:
        instance._mptt_cached_fields[field_name] = opts.get_raw_field_value(instance, field_name)

def post_init(instance, **kwargs):
    """
    Caches (in an instance._mptt_cached_fields dict) the original values of:
     - parent pk
     - fields specified in order_insertion_by
    
    These are used in pre_save to determine if the relevant fields have changed,
    so that the MPTT fields need to be updated.
    """
    _update_mptt_cached_fields(instance)


def _insertion_target_filters(node, order_insertion_by):
    """
    Creates a filter which matches suitable right siblings for ``node``,
    where insertion should maintain ordering according to the list of
    fields in ``order_insertion_by``.

    For example, given an ``order_insertion_by`` of
    ``['field1', 'field2', 'field3']``, the resulting filter should
    correspond to the following SQL::

       field1 > %s
       OR (field1 = %s AND field2 > %s)
       OR (field1 = %s AND field2 = %s AND field3 > %s)

    """
    fields = []
    filters = []
    for field in order_insertion_by:
        value = getattr(node, field)
        filters.append(reduce(operator.and_, [Q(**{f: v}) for f, v in fields] +
                                             [Q(**{'%s__gt' % field: value})]))
        fields.append((field, value))
    return reduce(operator.or_, filters)

def _get_ordered_insertion_target(node, parent):
    """
    Attempts to retrieve a suitable right sibling for ``node``
    underneath ``parent`` (which may be ``None`` in the case of root
    nodes) so that ordering by the fields specified by the node's class'
    ``order_insertion_by`` option is maintained.

    Returns ``None`` if no suitable sibling can be found.
    """
    right_sibling = None
    # Optimisation - if the parent doesn't have descendants,
    # the node will always be its last child.
    if parent is None or parent.get_descendant_count() > 0:
        opts = node._mptt_meta
        order_by = opts.order_insertion_by[:]
        filters = _insertion_target_filters(node, order_by)
        if parent:
            filters = filters & Q(**{opts.parent_attr: parent})
            # Fall back on tree ordering if multiple child nodes have
            # the same values.
            order_by.append(opts.left_attr)
        else:
            filters = filters & Q(**{'%s__isnull' % opts.parent_attr: True})
            # Fall back on tree id ordering if multiple root nodes have
            # the same values.
            order_by.append(opts.tree_id_attr)
        queryset = node._default_manager.filter(filters).order_by(*order_by)
        if node.pk:
            queryset = queryset.exclude(pk=node.pk)
        try:
            right_sibling = queryset[:1][0]
        except IndexError:
            # No suitable right sibling could be found
            pass
    return right_sibling

def pre_save(instance, **kwargs):
    """
    If this is a new node, sets tree fields up before it is inserted
    into the database, making room in the tree structure as neccessary,
    defaulting to making the new node the last child of its parent.

    It the node's left and right edge indicators already been set, we
    take this as indication that the node has already been set up for
    insertion, so its tree fields are left untouched.

    If this is an existing node and its parent has been changed,
    performs reparenting in the tree structure, defaulting to making the
    node the last child of its new parent.

    In either case, if the node's class has its ``order_insertion_by``
    tree option set, the node will be inserted or moved to the
    appropriate position to maintain ordering by the specified field.
    """
    if kwargs.get('raw'):
        return
    
    opts = instance._mptt_meta
    parent_id = opts.get_raw_field_value(instance, opts.parent_attr)
    if not instance.pk:
        if (getattr(instance, opts.left_attr) and
            getattr(instance, opts.right_attr)):
            # This node has already been set up for insertion.
            return
        
        parent = getattr(instance, opts.parent_attr)

        if opts.order_insertion_by:
            right_sibling = _get_ordered_insertion_target(instance, parent)
            if right_sibling:
                instance.insert_at(right_sibling, 'left')
                return

        # Default insertion
        instance.insert_at(parent, position='last-child')
    else:
        old_parent_id = instance._mptt_cached_fields[opts.parent_attr]
        same_order = old_parent_id == parent_id
        if same_order and len(instance._mptt_cached_fields) > 1:
            for field_name, old_value in instance._mptt_cached_fields.items():
                if old_value != opts.get_raw_field_value(instance, field_name):
                    same_order = False
                    break
        
        if not same_order:
            opts.set_raw_field_value(instance, opts.parent_attr, old_parent_id)
            try:
                if opts.order_insertion_by:
                    right_sibling = _get_ordered_insertion_target(instance,
                                    getattr(instance, opts.parent_attr))
                    if right_sibling:
                        instance.move_to(right_sibling, 'left')
                        return

                # Default movement
                if parent_id is None:
                    root_nodes = instance._tree_manager.root_nodes()
                    try:
                        rightmost_sibling = root_nodes.exclude(pk=instance.pk).order_by('-%s' % opts.tree_id_attr)[0]
                        instance.move_to(rightmost_sibling, position='right')
                    except IndexError:
                        pass
                else:
                    parent = getattr(instance, opts.parent_attr)
                    instance.move_to(parent, position='last-child')
            finally:
                # Make sure the instance's new parent is always
                # restored on the way out in case of errors.
                opts.set_raw_field_value(instance, opts.parent_attr, parent_id)

def post_save(instance, **kwargs):
    _update_mptt_cached_fields(instance)
