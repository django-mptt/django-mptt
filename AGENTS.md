# django-mptt — agent notes

## Project status

Officially unmaintained but kept alive on a best-effort basis. The goal is
compatibility with supported Django/Python versions and fixing bugs that have
a clear, self-contained reproduction. New features will not be added.

The fundamental limitation of MPTT is write amplification: every insert,
move, or delete touches many rows. This makes concurrent writes, bulk
operations, and any out-of-MPTT writes (raw SQL, `bulk_update`) inherently
risky. See `README.rst` and `docs/models.rst` for the documented caveats.

## Working conventions

### Commits
- No attribution line (`Co-Authored-By` etc.) — plain commit messages only.
- Commit message style: short imperative subject, blank line, then a paragraph
  explaining *why* (the bug mechanism, not just what changed).
- Include `(fixes #NNN)` in the subject when closing an issue.
- Commit AGENTS.md changes, CHANGELOG updates, and code/tests together in
  one commit per logical fix.

### Issues
- Always read the full issue body AND comments before acting.
- Close noisy issues (support questions, feature requests, third-party
  integrations, stale old-version reports) with a polite message referencing
  #833 and, where relevant, pointing to docs or Stack Overflow.
- For bugs: write a failing test first, then fix, then verify the test passes.
- When closing a PR from a first-time contributor, thank them and explain
  clearly why it is not being merged.

### CHANGELOG
- Add entries under "Next version" for every user-visible change.
- Use release dates in headings: `0.18 (2025-08-26)` format.
- One bullet per fix, starting with the affected symbol in backticks.

### Releases
- Not automatic; a human runs `make-release` (in `~/_dotfiles/bin`), which
  bumps `mptt/__init__.py`, dates the CHANGELOG section, commits, tags and
  pushes; the tag triggers the PyPI publish workflow.
- Keep a `0.NN (unreleased)` heading directly below "Next version" so
  `make-release` picks it up as the default version. Dry run:
  `make-release --dry-run`.

### Linting
- CI installs an unpinned ruff and runs `ruff check`; new ruff releases can
  enable new default rules and break CI on main. Run `uvx ruff check` (latest)
  and keep the pre-commit ruff rev in sync.

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
  to `"- Select an option -"` in Django 6.1. Guarded with
  `django.VERSION < (6, 1)` in `tests/myapp/test_forms.py`.
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

## Stale instances, #257 / #568 / #483 (fixed after 0.19)

- `TreeManager.move_node()` (and therefore `move_to()`) now reloads the tree
  fields of node and target, plus the node's parent and its
  `_mptt_cached_fields` entry, before moving (skipped inside
  `delay_mptt_updates()`). Regression tests: `StaleInstanceMoveTests`.
- The exact loop from #568 does not reproduce on current code; only its
  stale-instance variants did.
- #483 point 1 was a `delay_mptt_updates()` bug: moving a node out of a tree
  only marked the destination tree as modified, so the old tree was never
  rebuilt. `_move_node()` now tracks the old tree_id too. The tests asserting
  `rght = 6` were updated to the correct `4`.
- #483 point 2 (tree_ids not consecutive) is cosmetic, not a bug.
- Still unfixable from MPTT's side: writes outside MPTT (raw SQL,
  `bulk_update`, `update()`) and concurrent writers. `transaction.atomic()` is
  not enough under READ COMMITTED or InnoDB's REPEATABLE READ (snapshot reads
  vs. current-read UPDATEs); tree writes must be serialized with a lock taken
  first in the transaction. Documented in `docs/technical_details.rst`
  (Concurrency). Building locking into MPTT would be a larger change.
