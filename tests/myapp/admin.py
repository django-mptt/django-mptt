from django.contrib import admin

from mptt.admin import MPTTModelAdmin

from myapp.models import Category


class CategoryAdmin(MPTTModelAdmin):
    pass


admin.site.register(Category, CategoryAdmin)
