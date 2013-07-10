import django.dispatch

# Behaves like Djangos normal pre-/post_save signals signals with the
# added arguments ``target`` and ``position`` that matches those of
# ``move_to``
node_moved = django.dispatch.Signal(providing_args=[
    'instance',
    'target',
    'position'
])
