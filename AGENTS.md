# django-mptt — agent notes

## Project status

Officially unmaintained but kept alive on a best-effort basis. The goal is
compatibility with supported Django/Python versions and fixing bugs that have
a clear, self-contained reproduction. New features will not be added.

The fundamental limitation of MPTT is write amplification: every insert,
move, or delete touches many rows. This makes concurrent writes, bulk
operations, and any out-of-MPTT writes (raw SQL, `bulk_update`) inherently
risky. See `README.rst` and `docs/models.rst` for the documented caveats.

## Test command

```
tox -e py313-djmain
```

Run a single test class:

```
tox -e py313-djmain -- -k OrderedInsertionSortingTestCase
```

The suite uses an in-memory SQLite database (`--keepdb` is set). A second
in-memory SQLite database (`secondary`) is configured for multi-DB tests.

## Architecture

| Layer | Location | Role |
|-------|----------|------|
| Model metaclass | `mptt/models.py` `MPTTModelBase` | Adds tree fields, wires up `TreeManager` |
| Model mixin | `mptt/models.py` `MPTTModel` | `save()`, `delete()`, `insert_at()`, traversal methods |
| Manager | `mptt/managers.py` `TreeManager` | Raw SQL tree operations, queryset helpers |
| Options | `mptt/models.py` `MPTTOptions` | Holds `order_insertion_by`, cached-field helpers |

Key invariants:
- `lft` < `rght`, and descendants' lft/rght are strictly within the parent's range.
- `tree_id` groups root nodes; a whole subtree shares a tree_id.
- `_mptt_cached_fields` (populated in `__init__` and refreshed after `save()`)
  stores the pre-save values of `parent` and all `order_insertion_by` fields.
  If these are stale relative to the DB, any save that triggers a move will
  corrupt the tree.

`@delegate_manager` routes decorated methods to `_base_manager` when set.
`_base_manager` is used only for MTI (multi-table inheritance) models, NOT for
proxy models (fixed in this session — proxy models now use their own manager so
queryset results are typed to the proxy class).

## What we fixed in this session

- **Django 6.x test compat** — `empty_label` default changed from `"---------"`
  to `"- Select an option -"`. Added `django.VERSION < (6, 2)` guard in tests.
- **`is_root_node()` for unsaved instances** — Was checking only `parent_id`
  (always None for unsaved objects). Now also checks the `parent` attribute.
- **`_is_saved()` for UUID PKs** — Was checking `pk is None`; UUID fields are
  never None. Switched to `_state.adding`.
- **`DraggableMPTTAdmin.tree_actions()` N+1** — Was calling `get_absolute_url()`
  per row; the `data-url` attribute it produced was never read by the JS.
  Removed the call and the attribute.
- **`delete_selected_tree` with proxy models** — `delay_mptt_updates()` rejects
  proxy models; the admin now calls it on the concrete model via
  `_tree_manager.tree_model._tree_manager`.
- **Proxy model queryset methods returning concrete instances** — `_base_manager`
  was set for proxy models, causing all `@delegate_manager` methods to return
  concrete-typed querysets. Proxy models now have `_base_manager = None`.
- **`get_queryset_descendants/ancestors` sibling bleed (#517)** — The bounding-
  box range filter was too broad; contiguous siblings in the input queryset
  could appear in results. Added a level constraint to each range Q.
- **`get_family()` bypassing MTI delegation (#709)** — Was using `filter()`
  directly instead of going through `_base_manager`.
- **`TreeRelatedFieldListFilter` with `to_field` FKs (#693)** — `field_choices()`
  and `queryset()` assumed the FK target was always `pk`. Both now use
  `self.rel_name`.
- **`list_editable` ValidationError not shown (#726)** — `mptt_results()` was
  yielding plain `list` objects. Django's `ResultList(list)` subclass is needed
  to carry `.form` for the template's error display.
- **`get_children()` slow after `get_cached_trees` (#587)** — Was building a
  `pk__in=[n.pk for n in _cached_children]` queryset. Now uses
  `_mptt_filter(parent=self)` with a pre-populated `_result_cache`.
- **Duplicate `tree_id` when reordering root nodes (#687)** — When iterating a
  pre-loaded queryset and saving each node after changing its
  `order_insertion_by` field, stale in-memory `tree_id` values caused
  `_make_sibling_of_root_node` to operate on the wrong DB row. Fixed by
  refreshing the four MPTT tree fields from the DB before the repositioning
  move (skipped inside `delay_mptt_updates()`).
- **`save(using=...)`/`delete(using=...)` ignoring the specified DB (#685)** —
  `_get_connection()` always went through the router (returning "default").
  Fixed: `_get_connection()` now uses `self._db` when set; `save()`, `delete()`,
  and `insert_at()` build a `db_manager()`-bound manager and use it for all
  tree operations.
- **Several documentation gaps** — `recursetree` limitations (pagination,
  `block.super`), `node_moved` signal state, `bulk_create` usage, migration
  rebuild pattern, `TreeForeignKey` must point to `'self'`.

## Remaining known bugs

### #568 / #483 — `move_to` leaves incorrect `rght` on ancestors

**Symptom:** After `move_to()`, a parent node's `rght` value is too large
(the test suite itself has wrong expected values that paper over this).
Issue #483 was filed by the original maintainer; issue #568 is a user report
with before/after CSV dumps showing `cat1.rght = 6` when it should be `14`.

**Root cause (hypothesis):** When a subtree is moved between parents,
`_close_gap` removes space from the old location and `_create_space` adds space
at the new location. The in-memory `rght` update on the old parent
(`_post_insert_update_cached_parent_right`) may not match the actual SQL
update, leaving the cached value inconsistent with the DB. This is compounded
when `move_to` is called in a loop with stale instances.

**Approach to fix:**
1. Write a minimal reproducer: create a tree, move one child out, check the
   old parent's `rght` directly from the DB (`refresh_from_db`).
2. Compare what the raw SQL (`_inter_tree_move_and_close_gap`) produces in the
   DB against what `_post_insert_update_cached_parent_right` sets in memory.
3. The fix is likely adding `refresh_from_db` for MPTT fields at the top of
   `move_node()` (similar to how `delete()` already does it), so that the move
   calculations start from current DB values rather than potentially-stale
   in-memory values.
4. Alternatively, look at the `mk/nomagic` branch
   (https://github.com/matthiask/django-mptt/compare/master...mk/nomagic) which
   avoids the in-memory calculations entirely by refreshing from the DB after
   each raw SQL operation.

### #257 — Tree fields out of sync (canonical corruption meta-issue)

**Symptom:** Any code path that modifies tree fields outside of MPTT (raw SQL,
`bulk_update`, `update()` on a queryset) leaves the tree in an inconsistent
state. Also: calling `move_to()` on an instance with stale MPTT attributes.

**What we fixed:** The `save()` path — when `order_insertion_by` or `parent`
changes, we now `refresh_from_db` the four MPTT tree fields before executing
the move. This prevents the stale-instance + save() corruption case.

**What remains:**
- `move_to()` with stale instances: `move_node()` in the manager does not
  refresh the node's tree fields from the DB before computing the move. Adding
  `node.refresh_from_db(fields=[left, right, tree_id, level])` at the start of
  `move_node()` (the public API entry point) would mirror what `delete()` does
  and what `save()` now does.
- Out-of-MPTT writes: cannot be defended against from MPTT's side; must be
  documented as requiring a subsequent `rebuild()`.

**Approach to fix `move_to` stale-instance case:**
```python
def move_node(self, node, target, position="last-child"):
    opts = node._mptt_meta
    node.refresh_from_db(fields=[
        opts.left_attr, opts.right_attr,
        opts.tree_id_attr, opts.level_attr,
    ])
    # ... rest of method unchanged
```
Verify this doesn't break the existing move_node tests and check query counts
for any tests using `assertNumQueries`.
