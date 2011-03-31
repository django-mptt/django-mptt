"""
Model fields for working with trees.
"""

from django.db import models
from mptt.forms import TreeNodeChoiceField

class TreeForeignKey(models.ForeignKey):
    """
    Extends the foreign key, but uses mptt's `TreeNodeChoiceField` as
    the default form field.
    
    This is useful if you are creating models that need automatically
    generated ModelForms to use the correct widgets.
    """
    
    def formfield(self, **kwargs):
        """
        Use MPTT's TreeNodeChoiceField
        """
        defaults = {'form_class': TreeNodeChoiceField}
        defaults.update(kwargs)
        return super(TreeForeignKey, self).formfield(**defaults)
