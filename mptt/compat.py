def remote_field(field):
    # remote_field is new in Django 1.9
    return field.remote_field if hasattr(field, 'remote_field') else getattr(field, 'rel', None)


def remote_model(field):
    # remote_field is new in Django 1.9
    return field.remote_field.model if hasattr(field, 'remote_field') else field.rel.to


def cached_field_value(instance, attr):
    try:
        # In Django 2.0, use the new field cache API
        field = instance._meta.get_field(attr)
        if field.is_cached(instance):
            return field.get_cached_value(instance)
    except AttributeError:
        cache_attr = '_%s_cache' % attr
        if hasattr(instance, cache_attr):
            return getattr(instance, cache_attr)
    return None
