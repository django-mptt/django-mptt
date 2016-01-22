from __future__ import unicode_literals

from django.conf import settings
from django.contrib.admin.templatetags.admin_list import (
    result_hidden_fields, _boolean_icon, result_headers)
from django.contrib.admin.utils import lookup_field, display_for_field
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.template import Library
from django.utils.encoding import smart_text, force_text
from django.utils.html import escape, escapejs, conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import get_language_bidi


register = Library()


MPTT_ADMIN_LEVEL_INDENT = getattr(settings, 'MPTT_ADMIN_LEVEL_INDENT', 10)
IS_GRAPPELLI_INSTALLED = True if 'grappelli' in settings.INSTALLED_APPS else False


def get_empty_value_display(cl):
    if hasattr(cl.model_admin, 'get_empty_value_display'):
        return cl.model_admin.get_empty_value_display()
    else:
        # Django < 1.9
        from django.contrib.admin.views.main import EMPTY_CHANGELIST_VALUE
        return EMPTY_CHANGELIST_VALUE


###
# Ripped from contrib.admin's (1.3.1) items_for_result tag.
# The only difference is we're indenting nodes according to their level.
def mptt_items_for_result(cl, result, form):
    """
    Generates the actual list of data.
    """
    first = True
    pk = cl.lookup_opts.pk.attname

    # #### MPTT ADDITION START
    # figure out which field to indent
    mptt_indent_field = getattr(cl.model_admin, 'mptt_indent_field', None)
    if not mptt_indent_field:
        for field_name in cl.list_display:
            try:
                f = cl.lookup_opts.get_field(field_name)
            except models.FieldDoesNotExist:
                if (mptt_indent_field is None and
                        field_name != 'action_checkbox'):
                    mptt_indent_field = field_name
            else:
                # first model field, use this one
                mptt_indent_field = field_name
                break
    # #### MPTT ADDITION END

    # figure out how much to indent
    mptt_level_indent = getattr(cl.model_admin, 'mptt_level_indent', MPTT_ADMIN_LEVEL_INDENT)

    for field_name in cl.list_display:
        row_class = ''
        try:
            f, attr, value = lookup_field(field_name, result, cl.model_admin)
        except (AttributeError, ObjectDoesNotExist):
            result_repr = get_empty_value_display(cl)
        else:
            if f is None:
                if field_name == 'action_checkbox':
                    row_class = ' class="action-checkbox"'
                allow_tags = getattr(attr, 'allow_tags', False)
                boolean = getattr(attr, 'boolean', False)
                if boolean:
                    allow_tags = True
                    result_repr = _boolean_icon(value)
                else:
                    result_repr = smart_text(value)
                # Strip HTML tags in the resulting text, except if the
                # function has an "allow_tags" attribute set to True.
                if not allow_tags:
                    result_repr = conditional_escape(result_repr)
                else:
                    result_repr = mark_safe(result_repr)
            else:
                if isinstance(f.rel, models.ManyToOneRel):
                    field_val = getattr(result, f.name)
                    if field_val is None:
                        result_repr = get_empty_value_display(cl)
                    else:
                        result_repr = escape(field_val)
                else:
                    try:
                        result_repr = display_for_field(value, f)
                    except TypeError:
                        # Changed in Django 1.9, now takes 3 arguments
                        result_repr = display_for_field(
                            value, f, get_empty_value_display(cl))

                if isinstance(f, models.DateField)\
                        or isinstance(f, models.TimeField)\
                        or isinstance(f, models.ForeignKey):
                    row_class = ' class="nowrap"'
        if force_text(result_repr) == '':
            result_repr = mark_safe('&nbsp;')

        # #### MPTT ADDITION START
        if field_name == mptt_indent_field:
            level = getattr(result, result._mptt_meta.level_attr)
            padding_attr = ' style="padding-%s:%spx"' % (
                'right' if get_language_bidi() else 'left',
                8 + mptt_level_indent * level)
        else:
            padding_attr = ''
        # #### MPTT ADDITION END

        # If list_display_links not defined, add the link tag to the first field
        if (first and not cl.list_display_links) or field_name in cl.list_display_links:
            table_tag = {True: 'th', False: 'td'}[first]
            first = False
            url = cl.url_for_result(result)
            # Convert the pk to something that can be used in Javascript.
            # Problem cases are long ints (23L) and non-ASCII strings.
            if cl.to_field:
                attr = str(cl.to_field)
            else:
                attr = pk
            value = result.serializable_value(attr)
            result_id = escapejs(value)
            # #### MPTT SUBSTITUTION START
            yield mark_safe('<%s%s%s><a href="%s"%s>%s</a></%s>' % (
                table_tag,
                row_class,
                padding_attr,
                url,
                (cl.is_popup and ' onclick="opener.dismissRelatedLookupPopup(window, &#39;%s&#39;); return false;"' % result_id or ''),  # noqa
                conditional_escape(result_repr),
                table_tag))
            # #### MPTT SUBSTITUTION END
        else:
            # By default the fields come from ModelAdmin.list_editable, but if we pull
            # the fields out of the form instead of list_editable custom admins
            # can provide fields on a per request basis
            if (form and field_name in form.fields and not (
                    field_name == cl.model._meta.pk.name and
                    form[cl.model._meta.pk.name].is_hidden)):
                bf = form[field_name]
                result_repr = mark_safe(force_text(bf.errors) + force_text(bf))
            else:
                result_repr = conditional_escape(result_repr)
            # #### MPTT SUBSTITUTION START
            yield mark_safe('<td%s%s>%s</td>' % (row_class, padding_attr, result_repr))
            # #### MPTT SUBSTITUTION END
    if form and not form[cl.model._meta.pk.name].is_hidden:
        yield mark_safe('<td>%s</td>' % force_text(form[cl.model._meta.pk.name]))


def mptt_results(cl):
    if cl.formset:
        for res, form in zip(cl.result_list, cl.formset.forms):
            yield list(mptt_items_for_result(cl, res, form))
    else:
        for res in cl.result_list:
            yield list(mptt_items_for_result(cl, res, None))


def mptt_result_list(cl):
    """
    Displays the headers and data list together
    """
    return {'cl': cl,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': list(result_headers(cl)),
            'results': list(mptt_results(cl))}

# custom template is merely so we can strip out sortable-ness from the column headers
# Based on admin/change_list_results.html (1.3.1)
if IS_GRAPPELLI_INSTALLED:
    mptt_result_list = register.inclusion_tag(
        "admin/grappelli_mptt_change_list_results.html")(mptt_result_list)
else:
    mptt_result_list = register.inclusion_tag(
        "admin/mptt_change_list_results.html")(mptt_result_list)
