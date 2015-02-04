from django.db import models

class TreeQuerySet(models.query.QuerySet):
    def get_descendants(self, *args, **kwargs):
        return self.model.objects.get_queryset_descendants(self, *args, **kwargs)

    def get_ancestors(self, *args, **kwargs):
        return self.model.objects.get_queryset_ancestors(self, *args, **kwargs)
