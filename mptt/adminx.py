
from xadmin.sites import site
from xadmin.views import BaseAdminPlugin, ListAdminView, ModelFormAdminView

from mptt.models import MPTTModel
from mptt.forms import MPTTAdminForm, TreeNodeChoiceField

class MPTTListPlugin(BaseAdminPlugin):

    def init_request(self, *args, **kwargs):
        return self.model and issubclass(self.model, MPTTModel)

    def get_ordering(self, __):
        tree_id = self.model._mptt_meta.tree_id_attr
        left = self.model._mptt_meta.left_attr
        return (tree_id, left)

    def result_item(self, __, obj, field_name, row):
        is_display = row['is_display_first']
        item = __()
        if is_display and not row['is_display_first']:
            item.wraps.append(u'%s %%s' % ('---' * obj.get_level()))
        return item

    # Media
    def get_media(self, media):
        #media.add_css({'screen': [self.static('xadmin/css/aggregation.css'),]})
        return media

site.register_plugin(MPTTListPlugin, ListAdminView)

class MPTTFormPlugin(BaseAdminPlugin):

    def init_request(self, *args, **kwargs):
        result = self.model and issubclass(self.model, MPTTModel)
        if result:
            self.admin_view.form = MPTTAdminForm
        return result

    def get_field_attrs(self, attrs, db_field, **kwargs):
        from mptt.models import MPTTModel, TreeForeignKey
        if db_field.rel and issubclass(db_field.rel.to, MPTTModel) \
                and not isinstance(db_field, TreeForeignKey) \
                and not db_field.name in self.raw_id_fields:
            attrs.update(dict(form_class=TreeNodeChoiceField, queryset=db_field.rel.to.objects.all(), required=False))
        return attrs

site.register_plugin(MPTTFormPlugin, ModelFormAdminView)
