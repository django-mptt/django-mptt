from django.db import connection

qn = connection.ops.quote_name

count_subquery = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s = %(mptt_table)s.%(mptt_pk)s
)"""

cumulative_count_subquery = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s IN
    (
        SELECT m2.%(mptt_pk)s
        FROM %(mptt_table)s m2
        WHERE m2.%(tree_id)s = %(mptt_table)s.%(tree_id)s
          AND m2.%(left)s BETWEEN %(mptt_table)s.%(left)s
                              AND %(mptt_table)s.%(right)s
    )
)"""

def create_count_subquery(mptt_cls, rel_cls, rel_field):
    """
    Creates a subquery for use with the ``select`` argument of the ORM's
    ``extra`` method, counting the number of ``rel_cls`` items which
    are related to ``mptt_cls`` items through its ``rel_field`` field.

    ``mptt_cls``
       An MPTT ``Model`` class or instance.

    ``rel_cls``
       A ``Model`` class which has a relation to ``mptt_cls``.

    ``rel_field``
       The name of the field in ``rel_cls`` which holds the relation
       to ``mptt_cls``.
    """
    return count_subquery % {
        'rel_table': qn(rel_cls._meta.db_table),
        'mptt_fk': qn(rel_cls._meta.get_field(rel_field).column),
        'mptt_table': qn(mptt_cls._meta.db_table),
        'mptt_pk': qn(mptt_cls._meta.pk.column),
    }

def create_cumulative_count_subquery(mptt_cls, rel_cls, rel_field):
    """
    Creates a subquery for use with the ``select`` argument of the ORM's
    ``extra`` method, counting the number of ``rel_cls`` items which
    are related to ``mptt_cls`` items and their descendants through its
    ``rel_field`` field.

    ``mptt_cls``
       An MPTT ``Model`` class or instance.

    ``rel_cls``
       A ``Model`` class which has a relation to ``mptt_cls``.

    ``rel_field``
       The name of the field in ``rel_cls`` which holds the relation
       to ``mptt_cls``.
    """
    opts = mptt_cls._meta
    tree = mptt_cls._tree_manager
    return cumulative_count_subquery % {
        'rel_table': qn(rel_cls._meta.db_table),
        'mptt_fk': qn(rel_cls._meta.get_field(rel_field).column),
        'mptt_table': qn(opts.db_table),
        'mptt_pk': qn(opts.pk.column),
        'tree_id': qn(opts.get_field(tree.tree_id_attr).column),
        'left': qn(opts.get_field(tree.left_attr).column),
        'right': qn(opts.get_field(tree.right_attr).column),
    }
