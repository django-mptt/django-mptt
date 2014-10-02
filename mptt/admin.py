from __future__ import unicode_literals
import django
from django.conf import settings
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin.options import ModelAdmin

from mptt.forms import MPTTAdminForm, TreeNodeChoiceField
from mptt.models import MPTTModel, TreeForeignKey

__all__ = ('MPTTModelAdmin', 'MPTTAdminForm')
IS_GRAPPELLI_INSTALLED = 'grappelli' in settings.INSTALLED_APPS


class MPTTModelAdmin(ModelAdmin):
    """
    A basic admin class that displays tree items according to their position in
    the tree.  No extra editing functionality beyond what Django admin normally
    offers.
    """

    if IS_GRAPPELLI_INSTALLED:
        change_list_template = 'admin/grappelli_mptt_change_list.html'
    else:
        change_list_template = 'admin/mptt_change_list.html'

    form = MPTTAdminForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if issubclass(db_field.rel.to, MPTTModel) \
                and not isinstance(db_field, TreeForeignKey) \
                and db_field.name not in self.raw_id_fields:
            defaults = dict(
                form_class=TreeNodeChoiceField,
                queryset=db_field.rel.to.objects.all(),
                required=False)
            defaults.update(kwargs)
            kwargs = defaults
        return super(MPTTModelAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs)

    def get_ordering(self, request):
        """
        Changes the default ordering for changelists to tree-order.
        """
        mptt_opts = self.model._mptt_meta
        return self.ordering or (mptt_opts.tree_id_attr, mptt_opts.left_attr)
