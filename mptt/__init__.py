
__all__ = ('VERSION',)

VERSION = (0, 4, 'pre')

def register(*args, **kwargs):
    """
    This method does nothing!
    It is included for backwards compatibility with existing libraries.
    You should inherit your model from mptt.models.MPTTModel instead of calling this.
    
    For libraries that have to support both django-mptt 0.3 and 0.4, see the Upgrade Notes in the documentation.
    """
    import warnings
    warnings.warn("mptt.register() is deprecated, does nothing, and will be removed in 0.5", DeprecationWarning)
