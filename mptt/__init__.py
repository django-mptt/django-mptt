
VERSION = (0, 4, 1, 'pre')

def register(*args, **kwargs):
    """
    Registers a model class as an MPTTModel, adding MPTT fields and adding MPTTModel to __bases__.
    This is equivalent to just subclassing MPTTModel, but works for an already-created model.
    
    This method was removed in 0.4.0, but restored in 0.4.2 after use-cases were
    reported that were impossible by merely subclassing MPTTModel.
    """
    from mptt.models import MPTTModelBase
    return MPTTModelBase.register(*args, **kwargs)
