from django.db import models

class TreeQuerySet(models.query.QuerySet):
    def get_descendants(self, include_self=False):
        if include_self:
            return self.model.objects.filter(
                tree_id=self.values("tree_id"),
                lft__gte=self.values("lft"),
                rght__lte=self.values("rght"),
            )
        else:
            return self.model.objects.filter(
                tree_id=self.values("tree_id"),
                lft__gt=self.values("lft"),
                rght__lt=self.values("rght"),
            )

    def get_ancestors(self, include_self=False):
        if include_self:
            return self.model.objects.filter(
                tree_id=self.values("tree_id"),
                lft__lte=self.values("lft"),
                rght__gte=self.values("rght"),
            )
        else:
            return self.model.objects.filter(
                tree_id=self.values("tree_id"),
                lft__lt=self.values("lft"),
                rght__gt=self.values("rght"),
            )
