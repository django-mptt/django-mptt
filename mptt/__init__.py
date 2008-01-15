from django.db.models import signals as model_signals
from django.db.models import FieldDoesNotExist, PositiveIntegerField
from django.dispatch import dispatcher
from django.utils.translation import ugettext as _

from mptt import models
from mptt.signals import pre_delete, pre_save
from mptt.managers import TreeManager

VERSION = (0, 2, 'pre')

__all__ = ('register',)

class AlreadyRegistered(Exception):
    """
    An attempt was made to register a model for MPTT more than once.
    """
    pass

registry = []

def register(model, parent_attr='parent', left_attr='lft', right_attr='rght',
             tree_id_attr='tree_id', level_attr='level',
             tree_manager_attr='tree', order_insertion_by=None):
    """
    Sets the given model class up for Modified Preorder Tree Traversal.
    """
    if model in registry:
        raise AlreadyRegistered(_('The model %s has already been registered.') % model.__name__)
    registry.append(model)

    # Add tree options to the model's Options
    opts = model._meta
    opts.parent_attr = parent_attr
    opts.right_attr = right_attr
    opts.left_attr = left_attr
    opts.tree_id_attr = tree_id_attr
    opts.level_attr = level_attr
    opts.tree_manager_attr = tree_manager_attr
    opts.order_insertion_by = order_insertion_by

    # Add tree fields if they do not exist
    for attr in [left_attr, right_attr, tree_id_attr, level_attr]:
        try:
            opts.get_field(attr)
        except FieldDoesNotExist:
            PositiveIntegerField(
                db_index=True, editable=False).contribute_to_class(model, attr)

    # Add tree methods for model instances
    setattr(model, 'get_ancestors', models.get_ancestors)
    setattr(model, 'get_children', models.get_children)
    setattr(model, 'get_descendants', models.get_descendants)
    setattr(model, 'get_descendant_count', models.get_descendant_count)
    setattr(model, 'get_next_sibling', models.get_next_sibling)
    setattr(model, 'get_previous_sibling', models.get_previous_sibling)
    setattr(model, 'get_root', models.get_root)
    setattr(model, 'get_siblings', models.get_siblings)
    setattr(model, 'insert_at', models.insert_at)
    setattr(model, 'is_child_node', models.is_child_node)
    setattr(model, 'is_leaf_node', models.is_leaf_node)
    setattr(model, 'is_root_node', models.is_root_node)
    setattr(model, 'move_to', models.move_to)

    # Add a custom tree manager
    TreeManager(parent_attr, left_attr, right_attr, tree_id_attr,
                level_attr).contribute_to_class(model, tree_manager_attr)
    setattr(model, '_tree_manager', getattr(model, tree_manager_attr))

    # Set up signal receivers to manage the tree when instances of the
    # model are about to be created, have their parent changed or be
    # deleted.
    dispatcher.connect(pre_save, signal=model_signals.pre_save, sender=model)
    dispatcher.connect(pre_delete, signal=model_signals.pre_delete, sender=model)
