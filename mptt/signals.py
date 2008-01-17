"""
Signal receiving functions which handle Modified Preorder Tree Traversal
related logic when model instances are about to be saved or deleted.
"""
from django.utils.translation import ugettext as _

__all__ = ('pre_save', 'pre_delete')

def _get_ordered_insertion_target(node, parent):
    """
    Attempts to retrieve a suitable right sibling for ``node``
    underneath ``parent`` so that ordering by the field specified by
    the node's class' ``order_insertion_by`` field is maintained.

    Returns ``None`` if no suitable sibling can be found.
    """
    right_sibling = None
    # Optimisation - if the parent doesn't have descendants,
    # the node will always be its last child.
    if parent is None or parent.get_descendant_count() > 0:
        opts = node._meta
        filters = {'%s__gt' % opts.order_insertion_by: getattr(node, opts.order_insertion_by)}
        order_by = [opts.order_insertion_by]
        if parent:
            filters[opts.parent_attr] = parent
            # Fall back on tree ordering if multiple child nodes have
            # the same name.
            order_by.append(opts.left_attr)
        else:
            filters['%s__isnull' % opts.parent_attr] = True
            # Fall back on tree id ordering if multiple root nodes have
            # the same name.
            order_by.append(opts.tree_id_attr)
        try:
            right_sibling = node._default_manager.filter(
                **filters).order_by(*order_by)[0]
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

    .. note::
       The ``raw`` argument accepted by ``Model.save()`` is not
       currently passed along when the ``pre_save`` signal is
       dispatched, but we check for it anyway for the benefit of people
       who need to use fixtures and are willing to apply the patch in
       ticket http://code.djangoproject.com/ticket/5422 to their own
       version of Django.

    """
    if kwargs.get('raw'):
        return

    opts = instance._meta
    parent = getattr(instance, opts.parent_attr)
    if not instance.pk:
        if (getattr(instance, opts.left_attr) and
            getattr(instance, opts.right_attr)):
            # This node has already been set up for insertion.
            return

        if opts.order_insertion_by:
            right_sibling = _get_ordered_insertion_target(instance, parent)
            if right_sibling:
                instance.insert_at(right_sibling, 'left')
                return

        # Default insertion
        instance.insert_at(parent, position='last-child')
    else:
        # TODO Is it possible to track the original parent so we
        #      don't have to look it up again on each save after the
        #      first?
        old_parent = getattr(instance._default_manager.get(pk=instance.pk),
                             opts.parent_attr)
        if parent != old_parent:
            setattr(instance, opts.parent_attr, old_parent)
            try:
                if opts.order_insertion_by:
                    right_sibling = _get_ordered_insertion_target(instance,
                                                                  parent)
                    if right_sibling:
                        instance.move_to(right_sibling, 'left')
                        return

                # Default movement
                instance.move_to(parent, position='last-child')
            finally:
                # Make sure the instance's new parent is always
                # restored on the way out in case of errors.
                setattr(instance, opts.parent_attr, parent)

def pre_delete(instance):
    """
    Updates tree node edge indicators which will by affected by the
    deletion of the given model instance and any descendants it may
    have, to ensure the integrity of the tree structure is
    maintained.
    """
    opts = instance._meta
    tree_width = (getattr(instance, opts.right_attr) -
                  getattr(instance, opts.left_attr) + 1)
    target_right = getattr(instance, opts.right_attr)
    tree_id = getattr(instance, opts.tree_id_attr)
    instance._tree_manager._close_gap(tree_width, target_right, tree_id)
