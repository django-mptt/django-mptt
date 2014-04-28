from __future__ import unicode_literals
import django
import warnings
from django.conf import settings
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin.options import ModelAdmin
from django.utils.translation import ugettext as _

from mptt.forms import MPTTAdminForm, TreeNodeChoiceField

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
        # in 1.7+, get_query_set gets defined by the base ChangeList and complains if it's called.
        # otherwise, we have to define it ourselves.
        get_query_set = get_queryset


class MPTTModelAdmin(ModelAdmin):
    """
    A basic admin class that displays tree items according to their position in the tree.
    No extra editing functionality beyond what Django admin normally offers.
    """

    if IS_GRAPPELLI_INSTALLED:
        change_list_template = 'admin/grappelli_mptt_change_list.html'
    else:
        change_list_template = 'admin/mptt_change_list.html'

    form = MPTTAdminForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        from mptt.models import MPTTModel, TreeForeignKey
        if issubclass(db_field.rel.to, MPTTModel) \
                and not isinstance(db_field, TreeForeignKey) \
                and not db_field.name in self.raw_id_fields:
            defaults = dict(form_class=TreeNodeChoiceField, queryset=db_field.rel.to.objects.all(), required=False)
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


if getattr(settings, 'MPTT_USE_FEINCMS', True):
    _feincms_tree_editor = None
    try:
        from feincms.admin.tree_editor import TreeEditor as _feincms_tree_editor
    except ImportError:
        pass

    if _feincms_tree_editor is not None:
        __all__ = tuple(list(__all__) + ['FeinCMSModelAdmin'])

        class FeinCMSModelAdmin(_feincms_tree_editor):
            """
            A ModelAdmin to add changelist tree view and editing capabilities.
            Requires FeinCMS to be installed.
            """

            form = MPTTAdminForm

            def __init__(self, *args, **kwargs):
                warnings.warn(
                    "mptt.admin.FeinCMSModelAdmin has been deprecated, use "
                    "feincms.admin.tree_editor.TreeEditor instead.",
                    UserWarning,
                )
                super(FeinCMSModelAdmin, self).__init__(*args, **kwargs)

            def _actions_column(self, obj):
                actions = super(FeinCMSModelAdmin, self)._actions_column(obj)
                # compatibility with Django 1.4 admin images (issue #191):
                # https://docs.djangoproject.com/en/1.4/releases/1.4/#django-contrib-admin
                if django.VERSION >= (1, 4):
                    admin_img_prefix = "%sadmin/img/" % settings.STATIC_URL
                else:
                    admin_img_prefix = "%simg/admin/" % settings.ADMIN_MEDIA_PREFIX
                actions.insert(0,
                    '<a href="add/?%s=%s" title="%s"><img src="%sicon_addlink.gif" alt="%s" /></a>' % (
                        self.model._mptt_meta.parent_attr,
                        obj.pk,
                        _('Add child'),
                        admin_img_prefix,
                        _('Add child')))

                if hasattr(obj, 'get_absolute_url'):
                    actions.insert(0,
                        '<a href="%s" title="%s" target="_blank"><img src="%sselector-search.gif" alt="%s" /></a>' % (
                            obj.get_absolute_url(),
                            _('View on site'),
                            admin_img_prefix,
                            _('View on site')))
                return actions

            def delete_selected_tree(self, modeladmin, request, queryset):
                """
                Deletes multiple instances and makes sure the MPTT fields get recalculated properly.
                (Because merely doing a bulk delete doesn't trigger the post_delete hooks.)
                """
                n = 0
                for obj in queryset:
                    obj.delete()
                    n += 1
                self.message_user(request, _("Successfully deleted %s items.") % n)

            def get_actions(self, request):
                actions = super(FeinCMSModelAdmin, self).get_actions(request)
                if 'delete_selected' in actions:
                    actions['delete_selected'] = (self.delete_selected_tree, 'delete_selected', _("Delete selected %(verbose_name_plural)s"))
                return actions
