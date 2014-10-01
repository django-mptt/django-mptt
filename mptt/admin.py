from __future__ import unicode_literals
import django
from django.conf import settings
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin.options import ModelAdmin

from mptt.forms import MPTTAdminForm, TreeNodeChoiceField
from mptt.models import MPTTModel, TreeForeignKey

__all__ = ('MPTTChangeList', 'MPTTModelAdmin', 'MPTTAdminForm')
IS_GRAPPELLI_INSTALLED = 'grappelli' in settings.INSTALLED_APPS


class MPTTChangeList(ChangeList):
    # rant: why oh why would you rename something so widely used?
    def get_queryset(self, request):
        super_ = super(MPTTChangeList, self)
        if django.VERSION < (1, 7):
            qs = super_.get_query_set(request)
        else:
            qs = super_.get_queryset(request)

        # always order by (tree_id, left)
        tree_id = qs.model._mptt_meta.tree_id_attr
        left = qs.model._mptt_meta.left_attr
        return qs.order_by(tree_id, left)

    if django.VERSION < (1, 7):
        # in 1.7+, get_query_set gets defined by the base ChangeList and
        # complains if it's called.  otherwise, we have to define it ourselves.
        get_query_set = get_queryset


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
        return super(MPTTModelAdmin, self).formfield_for_foreignkey(db_field,
                                                                    request,
                                                                    **kwargs)

    def get_changelist(self, request, **kwargs):
        """
        Returns the ChangeList class for use on the changelist page.
        """
        return MPTTChangeList
