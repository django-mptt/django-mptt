import xadmin
from models import Genre

class GenreAdmin(object):
    list_display = ('name', 'parent', )
    list_display_links = ('name',)
    search_fields = ['name']
    
xadmin.site.register(Genre, GenreAdmin)
