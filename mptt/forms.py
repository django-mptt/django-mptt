from django import newforms as forms
from django.newforms.forms import NON_FIELD_ERRORS
from django.newforms.util import ErrorList
from django.utils.translation import ugettext_lazy as _

from mptt.exceptions import InvalidMove

class MoveNodeForm(forms.Form):
    """
    A basic form for moving a node around its tree.
    """
    POSITION_FIRST_CHILD = 'first-child'
    POSITION_LAST_CHILD = 'last-child'
    POSITION_LEFT = 'left'
    POSITION_RIGHT = 'right'

    POSITION_CHOICES = (
        (POSITION_FIRST_CHILD, _('First child')),
        (POSITION_LAST_CHILD, _('Last child')),
        (POSITION_LEFT, _('Left sibling')),
        (POSITION_RIGHT, _('Right sibling')),
    )

    target   = forms.ModelChoiceField(queryset=None)
    position = forms.ChoiceField(choices=POSITION_CHOICES,
                                 initial=POSITION_FIRST_CHILD)

    def __init__(self, node, *args, **kwargs):
        """
        A ``valid_targets`` keyword argument can be used to provide a
        ``QuerySet`` of valid targets for the move - for example, if you
        want to restrict the node to moving within its own tree, pass a
        ``QuerySet`` containing everything in the node's tree except
        itself and its descendants (to prevent invalid moves) and the
        root node (as a user could choose to make the node a sibling of
        the root node).

        If ``valid_targets`` is not provided, the list of valid targets
        will consist of everything in the tree for the node's class
        apart from the node itself and any descendants.
        """
        valid_targets = kwargs.pop('valid_targets', None)
        super(MoveNodeForm, self).__init__(*args, **kwargs)
        self.node = node
        opts = node._meta
        if valid_targets is None:
            valid_targets = node._tree_manager.exclude(**{
                opts.tree_id_attr: getattr(node, opts.tree_id_attr),
                '%s__gte' % opts.left_attr: getattr(node, opts.left_attr),
                '%s__lte' % opts.right_attr: getattr(node, opts.right_attr),
            })
        self.fields['target'].queryset = valid_targets
        self.fields['target'].choices = \
            [(target.pk, '%s %s' % ('---' * getattr(target, opts.level_attr),
                                    unicode(target)))
             for target in valid_targets]

    def save(self):
        """
        Attempts to move the node using the selected target and
        position.

        If an invalid move is attempted, the related error message will
        be added to the form's non-field errors and the error will be
        re-raised. Callers should attempt to catch ``InvalidNode`` to
        redisplay the form with the error, should it occur.
        """
        try:
            self.node.move_to(self.cleaned_data['target'],
                              self.cleaned_data['position'])
            return self.node
        except InvalidMove, e:
            self.errors[NON_FIELD_ERRORS] = ErrorList(e)
            raise
