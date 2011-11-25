
VERSION = (0, 5, 2)


# NOTE: This method was removed in 0.4.0, but restored in 0.4.2 after use-cases were
# reported that were impossible by merely subclassing MPTTModel.
def register(*args, **kwargs):
    """
    Registers a model class as an MPTTModel, adding MPTT fields and adding MPTTModel to __bases__.
    This is equivalent to just subclassing MPTTModel, but works for an already-created model.
    """
    from mptt.models import MPTTModelBase
    return MPTTModelBase.register(*args, **kwargs)


# Also removed in 0.4.0 but restored in 0.4.2, otherwise this 0.3-compatibility code will break:
#     if hasattr(mptt, 'register'):
#         try:
#             mptt.register(...)
#         except mptt.AlreadyRegistered:
#             pass

class AlreadyRegistered(Exception):
    "Deprecated - don't use this anymore. It's never thrown, you don't need to catch it"
