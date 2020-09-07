from django.contrib import admin
from myapp.models import Category, Person

from mptt.admin import DraggableMPTTAdmin, MPTTModelAdmin


class CategoryAdmin(MPTTModelAdmin):
    pass


admin.site.register(Category, CategoryAdmin)
admin.site.register(Person, DraggableMPTTAdmin)
