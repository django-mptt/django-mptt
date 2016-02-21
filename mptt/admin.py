from __future__ import unicode_literals

import json

from django import http
from django.conf import settings
from django.contrib.admin.actions import delete_selected
from django.contrib.admin.options import ModelAdmin
from django.db import IntegrityError, transaction
from django.forms.utils import flatatt
from django.templatetags.static import static
from django.utils.encoding import force_text
from django.utils.html import format_html, mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy

from mptt.exceptions import InvalidMove
from mptt.forms import MPTTAdminForm, TreeNodeChoiceField
from mptt.models import MPTTModel, TreeForeignKey

__all__ = ('MPTTModelAdmin', 'MPTTAdminForm', 'DraggableMPTTAdmin')
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


class JS(object):
    """
    Use this to insert a script tag via ``forms.Media`` containing additional
    attributes (such as ``id`` and ``data-*`` for CSP-compatible data
    injection.)::

        media.add_js([
            JS('asset.js', {
                'id': 'asset-script',
                'data-the-answer': '"42"',
            }),
        ])

    The rendered media tag (via ``{{ media.js }}`` or ``{{ media }}`` will
    now contain a script tag as follows, without line breaks::

        <script type="text/javascript" src="/static/asset.js"
            data-answer="&quot;42&quot;" id="asset-script"></script>

    The attributes are automatically escaped. The data attributes may now be
    accessed inside ``asset.js``::

        var answer = document.querySelector('#asset-script').dataset.answer;
    """
    def __init__(self, js, attrs):
        self.js = js
        self.attrs = attrs

    def startswith(self, _):
        # Masquerade as absolute path so that we are returned as-is.
        return True

    def __html__(self):
        return format_html(
            '{}"{}',
            static(self.js),
            mark_safe(flatatt(self.attrs)),
        ).rstrip('"')


class DraggableMPTTAdmin(MPTTModelAdmin):
    """
    The ``DraggableMPTTAdmin`` modifies the standard Django administration
    change list to a drag-drop enabled interface.
    """

    change_list_template = None  # Back to default
    list_per_page = 2000  # This will take a really long time to load.
    list_display = ('tree_actions', 'indented_title')  # Sane defaults.
    list_display_links = ('indented_title',)  # Sane defaults.
    mptt_level_indent = 20

    def tree_actions(self, item):
        try:
            url = item.get_absolute_url()
        except Exception:  # Nevermind.
            url = ''

        return format_html(
            '<div class="drag-handle"></div>'
            '<div class="tree-node" data-pk="{}" data-level="{}"'
            ' data-url="{}"></div>',
            item.pk,
            item._mpttfield('level'),
            url,
        )
    tree_actions.short_description = ''

    def indented_title(self, item):
        """
        Generate a short title for an object, indent it depending on
        the object's depth in the hierarchy.
        """
        return format_html(
            '<div style="text-indent:{}px">{}</div>',
            item._mpttfield('level') * self.mptt_level_indent,
            item,
        )
    indented_title.short_description = ugettext_lazy('title')

    def changelist_view(self, request, *args, **kwargs):
        if request.is_ajax() and request.POST.get('cmd') == 'move_node':
            return self._move_node(request)

        response = super(DraggableMPTTAdmin, self).changelist_view(
            request, *args, **kwargs)

        try:
            response.context_data['media'].add_css({'all': (
                'mptt/draggable-admin.css',
            )})
            response.context_data['media'].add_js((
                JS('mptt/draggable-admin.js', {
                    'id': 'draggable-admin-context',
                    'data-context': json.dumps(self._tree_context(request)),
                }),
            ),)
        except (AttributeError, KeyError):
            # Not meant for us if there is no context_data attribute (no
            # TemplateResponse) or no media in the context.
            pass

        return response

    @transaction.atomic
    def _move_node(self, request):
        position = request.POST.get('position')
        if position not in ('last-child', 'left', 'right'):
            self.message_user(request, _('Did not understand moving instruction.'))
            return http.HttpResponse('FAIL, unknown instruction.')

        queryset = self.get_queryset(request)
        try:
            cut_item = queryset.get(pk=request.POST.get('cut_item'))
            pasted_on = queryset.get(pk=request.POST.get('pasted_on'))
        except (self.model.DoesNotExist, TypeError, ValueError):
            self.message_user(request, _('Objects have disappeared, try again.'))
            return http.HttpResponse('FAIL, invalid objects.')

        if not self.has_change_permission(request, cut_item):
            self.message_user(request, _('No permission'))
            return http.HttpResponse('FAIL, no permission.')

        try:
            self.model._tree_manager.move_node(cut_item, pasted_on, position)
        except InvalidMove as e:
            self.message_user(request, '%s' % e)
            return http.HttpResponse('FAIL, invalid move.')
        except IntegrityError as e:
            self.message_user(request, _('Database error: %s') % e)
            raise

        self.message_user(
            request,
            _('%s has been successfully moved.') % cut_item)
        return http.HttpResponse('OK, moved.')

    def _tree_context(self, request):
        opts = self.model._meta

        return {
            'storageName': 'tree_%s_%s_collapsed' % (opts.app_label, opts.model_name),
            'treeStructure': self._build_tree_structure(self.get_queryset(request)),
            'levelIndent': self.mptt_level_indent,
            'messages': {
                'before': _('move node before node'),
                'child': _('move node to child position'),
                'after': _('move node after node'),
                'collapseTree': _('Collapse tree'),
                'expandTree': _('Expand tree'),
            },
        }

    def _build_tree_structure(self, queryset):
        """
        Build an in-memory representation of the item tree, trying to keep
        database accesses down to a minimum. The returned dictionary looks like
        this (as json dump):

            {"6": [7, 8, 10]
             "7": [12],
             ...
             }

        Leaves are not included in the dictionary.
        """
        all_nodes = {}

        mptt_opts = self.model._mptt_meta
        items = queryset.values_list(
            'pk',
            '%s_id' % mptt_opts.parent_attr,
        )
        for p_id, parent_id in items:
            all_nodes.setdefault(
                str(parent_id) if parent_id else 0,
                [],
            ).append(p_id)
        return all_nodes
