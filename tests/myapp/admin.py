from django.contrib import admin

from mptt.admin import MPTTModelAdmin, TreeEditor

from myapp.models import Category, Person


class CategoryAdmin(MPTTModelAdmin):
    pass


admin.site.register(Category, CategoryAdmin)
admin.site.register(Person, TreeEditor)
