from django.db import models
from django.db.models import signals as model_signals
from django.db.models.base import ModelBase

from mptt import signals
from mptt.managers import TreeManager

class MPTTOptions(object):
    """
    Options class for MPTT models. Use this as an inner class called MPTTMeta:
    
    class MyModel(MPTTModel):
        class MPTTMeta:
            order_insertion_by = ['name']
            parent_attr = 'myparent'
        ...     
    """
    
    order_insertion_by = []
    tree_manager_attr = 'tree'
    left_attr = 'lft'
    right_attr = 'rght'
    tree_id_attr = 'tree_id'
    level_attr = 'level'
    parent_attr = 'parent'
    
    def __init__(self, opts=None, **kwargs):
        # Override defaults with options provided
        if opts:
            opts = opts.__dict__.items()
        else:
            opts = []
        opts.extend(kwargs.items())
        
        for key, value in opts:
            setattr(self, key, value)
        
        # Normalize order_insertion_by to a list
        if isinstance(self.order_insertion_by, basestring):
            self.order_insertion_by = [self.order_insertion_by]
        elif isinstance(self.order_insertion_by, tuple):
            self.order_insertion_by = list(self.order_insertion_by)
        elif self.order_insertion_by is None:
            self.order_insertion_by = []
    
    def __iter__(self):
        return iter([(k, v) for (k, v) in self.__dict__.items() if not k.startswith('_')])
    
    # Helper methods for accessing tree attributes on models.
    def get_raw_field_value(self, instance, field_name):
        """
        Gets the value of the given fieldname for the instance.
        This is not the same as getattr().
        This function will return IDs for foreignkeys etc, rather than doing
        a database query.
        """
        field = instance._meta.get_field(field_name)
        return field.value_from_object(instance)
    
    def set_raw_field_value(self, instance, field_name, value):
        """
        Sets the value of the given fieldname for the instance.
        This is not the same as setattr().
        This function requires an ID for a foreignkey (etc) rather than an instance.
        """
        field = instance._meta.get_field(field_name)
        setattr(instance, field.attname, value)


class MPTTModelBase(ModelBase):
    """
    Metaclass for MPTT models
    """
    
    def __new__(meta, class_name, bases, class_dict):
        """
        Create subclasses of MPTTModel. This:
         - adds the MPTT fields to the class
         - adds a TreeManager to the model
        """
        class_dict['_mptt_meta'] = MPTTOptions(class_dict.pop('MPTTMeta', None))
        cls = super(MPTTModelBase, meta).__new__(meta, class_name, bases, class_dict)
        
        return meta.register(cls)
    
    @classmethod
    def register(meta, cls, **kwargs):
        """
        For the weird cases when you need to add tree-ness to an *existing*
        class. For other cases you should subclass MPTTModel instead of calling this.
        """
        
        if not hasattr(cls, '_mptt_meta'):
            cls._mptt_meta = MPTTOptions(**kwargs)
        
        abstract = getattr(cls._meta, 'abstract', False)
        
        # For backwards compatibility with existing libraries, we copy the 
        # _mptt_meta options into _meta.
        # This will be removed in 0.5.
        # All new code should use _mptt_meta rather than _meta for tree attributes.
        for attr in ('left_attr', 'right_attr', 'tree_id_attr', 'level_attr', 'parent_attr',
                    'tree_manager_attr', 'order_insertion_by'):
            setattr(cls._meta, attr, getattr(cls._mptt_meta, attr))
        
        try:
            MPTTModel
        except NameError:
            # We're defining the base class right now, so don't do anything
            # We only want to add this stuff to the subclasses.
            # (Otherwise if field names are customized, we'll end up adding two
            # copies)
            pass
        else:
            if not issubclass(cls, MPTTModel):
                cls.__bases__.insert(0, MPTTModel)
            
            for key in ('left_attr', 'right_attr', 'tree_id_attr', 'level_attr'):
                field_name = getattr(cls._mptt_meta, key)
                try:
                    cls._meta.get_field(field_name)
                except models.FieldDoesNotExist:
                    field = models.PositiveIntegerField(db_index=True, editable=False)
                    field.contribute_to_class(cls, field_name)
            
            # Add a custom tree manager
            if not abstract:
                manager = TreeManager(cls._mptt_meta)
                manager.contribute_to_class(cls, cls._mptt_meta.tree_manager_attr)
                setattr(cls, '_tree_manager', getattr(cls, cls._mptt_meta.tree_manager_attr))
            
            # Set up signal receivers
            model_signals.post_init.connect(signals.post_init, sender=cls)
            model_signals.pre_save.connect(signals.pre_save, sender=cls)
            model_signals.post_save.connect(signals.post_save, sender=cls)

        return cls

class MPTTModel(models.Model):
    """
    Base class for tree models.
    """
    
    __metaclass__ = MPTTModelBase
    
    class Meta:
        abstract = True
    
    def _mpttfield(self, fieldname):
        translated_fieldname = getattr(self._mptt_meta, '%s_attr' % fieldname)
        return getattr(self, translated_fieldname)
    
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

        opts = self._mptt_meta
        
        order_by = opts.left_attr
        if ascending:
            order_by = '-%s' % order_by
        
        qs = self._tree_manager._mptt_filter(
            left__lt=self._mpttfield('left'),
            right__gt=self._mpttfield('right'),
            tree_id=self._mpttfield('tree_id'),
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

        opts = self._mptt_meta
        left = getattr(self, opts.left_attr)
        right = getattr(self, opts.right_attr)
        
        if not include_self:
            left += 1
            right -= 1
        
        return self._tree_manager._mptt_filter(
            tree_id=self._mpttfield('tree_id'),
            left__gte=left,
            left__lte=right
        )

    def get_descendant_count(self):
        """
        Returns the number of descendants this model instance has.
        """
        return (self._mpttfield('right') -
                self._mpttfield('left') - 1) / 2

    def get_leafnodes(self, include_self=False):
        """
        Creates a ``QuerySet`` containing leafnodes of this model
        instance, in tree order.

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance (if it is a leaf node)
        """
        descendants = self.get_descendants(include_self=include_self)
        
        return self._tree_manager._mptt_filter(descendants,
            left=models.F(self._mptt_meta.right_attr)-1
        )

    def get_next_sibling(self, **filters):
        """
        Returns this model instance's next sibling in the tree, or
        ``None`` if it doesn't have a next sibling.
        """
        qs = self._tree_manager.filter(**filters)
        if self.is_root_node():
            qs = self._tree_manager._mptt_filter(qs,
                parent__isnull=True,
                tree_id__gt=self._mpttfield('tree_id'),
            )
        else:
            qs = self._tree_manager._mptt_filter(qs,
                parent__id=getattr(self, '%s_id' % self._mptt_meta.parent_attr),
                left__gt=self._mpttfield('right'),
            )
        
        siblings = qs[:1]
        return siblings and siblings[0] or None

    def get_previous_sibling(self, **filters):
        """
        Returns this model instance's previous sibling in the tree, or
        ``None`` if it doesn't have a previous sibling.
        """
        opts = self._mptt_meta
        qs = self._tree_manager.filter(**filters)
        if self.is_root_node():
            qs = self._tree_manager._mptt_filter(qs,
                parent__isnull=True,
                tree_id__lt=self._mpttfield('tree_id'),
            )
            qs = qs.order_by('-%s' % opts.tree_id_attr)
        else:
            qs = self._tree_manager._mptt_filter(qs,
                parent__id=getattr(self, '%s_id' % opts.parent_attr),
                right__lt=self._mpttfield('left'),
            )
            qs = qs.order_by('-%s' % opts.right_attr)

        siblings = qs[:1]
        return siblings and siblings[0] or None

    def get_root(self):
        """
        Returns the root node of this model instance's tree.
        """
        if self.is_root_node() and type(self) == self._tree_manager.tree_model:
            return self
        
        return self._tree_manager._mptt_filter(
            tree_id=self._mpttfield('tree_id'),
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
            parent_id = getattr(self, '%s_id' % self._mptt_meta.parent_attr)
            queryset = self._tree_manager._mptt_filter(parent__id=parent_id)
        if not include_self:
            queryset = queryset.exclude(pk=self.pk)
        return queryset

    def get_level(self):
        """
        Returns the level of this node (distance from root)
        """
        return getattr(self, self._mptt_meta.level_attr)

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
        return getattr(self, '%s_id' % self._mptt_meta.parent_attr) is None
    
    def is_descendant_of(self, other, include_self=False):
        """
        Returns ``True`` if this model is a descendant of the given node,
        ``False`` otherwise.
        If include_self is True, also returns True if the two nodes are the same node.
        """
        opts = self._mptt_meta
        
        if include_self and other.pk == self.pk:
            return True
        
        if getattr(self, opts.tree_id_attr) != getattr(other, opts.tree_id_attr):
            return False
        else:
            left = getattr(self, opts.left_attr)
            right = getattr(self, opts.right_attr)
            
            return left > getattr(other, opts.left_attr) and right < getattr(other, opts.right_attr)
    
    def is_ancestor_of(self, other, include_self=False):
        """
        Returns ``True`` if this model is an ancestor of the given node,
        ``False`` otherwise.
        If include_self is True, also returns True if the two nodes are the same node.
        """
        if include_self and other.pk == self.pk:
            return True
        return other.is_descendant_of(self)

    def move_to(self, target, position='first-child'):
        """
        Convenience method for calling ``TreeManager.move_node`` with this
        model instance.
        """
        self._tree_manager.move_node(self, target, position)

    def delete(self, *args, **kwargs):
        tree_width = (self._mpttfield('right') -
                      self._mpttfield('left') + 1)
        target_right = self._mpttfield('right')
        tree_id = self._mpttfield('tree_id')
        self._tree_manager._close_gap(tree_width, target_right, tree_id)
        super(MPTTModel, self).delete(*args, **kwargs)
    
