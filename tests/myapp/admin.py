from django.contrib import admin
from myapp.models import Category, Person

from mptt.admin import DraggableMPTTAdmin, MPTTModelAdmin


@admin.register(Category)
class CategoryAdmin(MPTTModelAdmin):
    pass


admin.site.register(Person, DraggableMPTTAdmin)
