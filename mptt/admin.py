from __future__ import unicode_literals

import json

from django import http
from django.conf import settings
from django.contrib.admin.actions import delete_selected
from django.contrib.admin.options import ModelAdmin
from django.utils.encoding import force_text
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from mptt.exceptions import InvalidMove
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
            db = kwargs.get('using')

            limit_choices_to = db_field.get_limit_choices_to()
            defaults = dict(
                form_class=TreeNodeChoiceField,
                queryset=db_field.rel.to._default_manager.using(
                    db).complex_filter(limit_choices_to),
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

    def delete_selected_tree(self, modeladmin, request, queryset):
        """
        Deletes multiple instances and makes sure the MPTT fields get
        recalculated properly. (Because merely doing a bulk delete doesn't
        trigger the post_delete hooks.)
        """
        # If this is True, the confirmation page has been displayed
        if request.POST.get('post'):
            n = 0
            with queryset.model._tree_manager.delay_mptt_updates():
                for obj in queryset:
                    if self.has_delete_permission(request, obj):
                        obj.delete()
                        n += 1
                        obj_display = force_text(obj)
                        self.log_deletion(request, obj, obj_display)
            self.message_user(
                request,
                _('Successfully deleted %(count)d items.') % {'count': n})
            # Return None to display the change list page again
            return None
        else:
            # (ab)using the built-in action to display the confirmation page
            return delete_selected(self, request, queryset)

    def get_actions(self, request):
        actions = super(MPTTModelAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            actions['delete_selected'] = (
                self.delete_selected_tree,
                'delete_selected',
                _('Delete selected %(verbose_name_plural)s'))
        return actions


class TreeEditor(MPTTModelAdmin):
    """
    The ``TreeEditor`` modifies the standard Django administration change list
    to a drag-drop enabled interface for django-mptt_-managed Django models.

    .. _django-mptt: https://github.com/django-mptt/django-mptt/
    """

    def __init__(self, *args, **kwargs):
        super(TreeEditor, self).__init__(*args, **kwargs)

        opts = self.model._meta
        self.change_list_template = [
            'admin/%s/%s/tree_editor.html' % (
                opts.app_label, opts.object_name.lower()),
            'admin/%s/tree_editor.html' % opts.app_label,
            'admin/tree_editor.html',
        ]

        # Set a better column header than "title"
        self.__class__.indented_title.short_description = opts.verbose_name

    def get_list_display(self, request):
        list_display = list(super(TreeEditor, self).get_list_display(request))
        list_display = [
            l for l in list_display
            if l not in ('__str__', '__unicode__')
        ]

        if 'indented_title' in list_display:
            return list_display

        place = 1 if 'action_checkbox' in list_display else 0
        list_display[place:place] = [
            'tree_actions',
            'indented_title',
        ]
        return list_display

    def get_list_display_links(self, request, list_display):
        return ('indented_title',)

    def tree_actions(self, item):
        try:
            url = item.get_absolute_url()
        except Exception:  # Yes.
            url = ''

        return mark_safe(' '.join((
            '<div class="drag_handle"></div>',
            (
                '<div id="tree_marker-%d" class="tree_marker"'
                ' data-url="%s"></div>'
            ) % (
                item.pk,
                escape(url),
            ),
        )))
    tree_actions.short_description = ''
    tree_actions.allow_tags = True

    def indented_title(self, item):
        """
        Generate a short title for an object, indent it depending on
        the object's depth in the hierarchy.
        """
        return mark_safe('<div style="width:%spx"></div> %s' % (
            item._mpttfield('level') * 20,
            escape('%s' % item),
        ))
    indented_title.short_description = _('title')
    indented_title.allow_tags = True

    def changelist_view(self, request, extra_context=None, *args, **kwargs):
        """
        Handle the changelist view, the django view for the model instances
        change list/actions page.
        """
        # handle common AJAX requests
        if request.is_ajax():
            cmd = request.POST.get('__cmd')
            if cmd == 'move_node':
                return self._move_node(request)
            return http.HttpResponseBadRequest(
                'Oops. AJAX request not understood.')

        extra_context = extra_context or {}
        extra_context['tree_editor_context'] = TreeEditorContext(self.get_queryset(request))

        return super(TreeEditor, self).changelist_view(
            request, extra_context, *args, **kwargs)

    def _move_node(self, request):
        if hasattr(self.model.objects, 'move_node'):
            tree_manager = self.model.objects
        else:
            tree_manager = self.model._tree_manager

        queryset = self.get_queryset(request)
        cut_item = queryset.get(pk=request.POST.get('cut_item'))
        pasted_on = queryset.get(pk=request.POST.get('pasted_on'))
        position = request.POST.get('position')

        if not self.has_change_permission(request, cut_item):
            self.message_user(request, _('No permission'))
            return http.HttpResponse('FAIL')

        if position in ('last-child', 'left', 'right'):
            try:
                tree_manager.move_node(cut_item, pasted_on, position)
            except InvalidMove as e:
                self.message_user(request, '%s' % e)
                return http.HttpResponse('FAIL')

            # Ensure that model save methods have been run - give everyone
            # a chance to clear caches etc.
            for item in queryset.filter(id__in=(cut_item.pk, pasted_on.pk)):
                item.save()

            self.message_user(
                request,
                _('%s has been moved to a new position.') % cut_item)
            return http.HttpResponse('OK')

        self.message_user(request, _('Did not understand moving instruction.'))
        return http.HttpResponse('FAIL')


class TreeEditorContext(object):
    def __init__(self, queryset):
        self.queryset = queryset
        self.model = queryset.model

    def context(self):
        opts = self.model._meta

        return json.dumps({
            'cookieName': 'tree_%s_%s_collapsed' % (opts.app_label, opts.model_name),
            'treeStructure': self.build_tree_structure(),
            'nodeLevels': dict(
                self.queryset.values_list(
                    'pk',
                    self.model._mptt_meta.level_attr,
                )
            ),
        })

    def build_tree_structure(self):
        """
        Build an in-memory representation of the item tree, trying to keep
        database accesses down to a minimum. The returned dictionary looks like
        this (as json dump):

            {"6": [7, 8, 10]
             "7": [12],
             "8": [],
             ...
             }
        """
        all_nodes = {}

        mptt_opts = self.model._mptt_meta
        items = self.queryset.values_list(
            'pk',
            '%s_id' % mptt_opts.parent_attr,
        )
        for p_id, parent_id in items:
            all_nodes.setdefault(
                str(parent_id) if parent_id else 0,
                [],
            ).append(p_id)
        return all_nodes
