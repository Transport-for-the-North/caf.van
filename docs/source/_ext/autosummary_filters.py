"""Add custom Jinja filters for use in autosummary templates.

Adds the `include_module_member` and `include_class_member` filters
which take an object name and return a boolean as to whether that
object should be included in the documentation.

The filters can be customised with the following variables in
the `autosummary_context`:

- "{module|class}_include_private"
- "{module|class}_include_special"
- "{module|class}_exclude_members"
- "{module|class}_include_members"
"""

from collections.abc import Collection, Mapping

from jinja2 import pass_context
from sphinx.application import Sphinx
from sphinx.ext.autosummary.generate import AutosummaryRenderer


def _is_special(value: str) -> bool:
    return value.startswith("__") and value.endswith("__")


def include_member(
    value: str,
    private: bool,
    special: bool,
    exclude_names: Collection[str] | None = None,
    include_names: Collection[str] | None = None,
) -> bool:
    """Include a named class (or module) member based soley on it's name."""
    if include_names is not None and value in include_names:
        return True
    if exclude_names is not None and value in exclude_names:
        return False
    if (private and special) or not value.startswith("_"):
        return True
    return bool(special and _is_special(value))


@pass_context
def _include_class_member(context: Mapping, value: str) -> bool:
    return include_member(
        value,
        private=context.get("class_include_private", True),
        special=context.get("class_include_special", True),
        exclude_names=context.get("class_exclude_members", None),
        include_names=context.get("class_include_members", None),
    )


@pass_context
def _include_module_member(context: Mapping, value: str) -> bool:
    return include_member(
        value,
        private=context.get("module_include_private", True),
        special=context.get("module_include_special", True),
        exclude_names=context.get("module_exclude_members", None),
        include_names=context.get("module_include_members", None),
    )


def add_autosummary_filters(app: Sphinx) -> None:
    """Patch AutosummaryRenderer init to include new jinja filters."""
    del app
    original = AutosummaryRenderer.__init__

    def patched(self, app):  # noqa: ANN001, ANN202
        original(self, app)
        self.env.filters["include_class_member"] = _include_class_member
        self.env.filters["include_module_member"] = _include_module_member

    AutosummaryRenderer.__init__ = patched


def setup(app: Sphinx) -> dict:
    """Patch autosummary with new Jinja filters."""
    app.connect("builder-inited", add_autosummary_filters)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
