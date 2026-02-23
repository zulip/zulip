"""Placeholder tests for nodl package.

These tests verify the basic nodl package structure is correct.
"""


def test_nodl_package_imports() -> None:
    """Test that nodl package can be imported."""
    import nodl

    assert nodl is not None


def test_nodl_apps_defined() -> None:
    """Test that NODL_APPS is properly defined."""
    from nodl.apps import NODL_APPS

    expected_apps = [
        "nodl.auth.apps.NodlAuthConfig",
        "nodl.sync",
        "nodl.extensions",
        "nodl.storage",
        "nodl.api",
    ]
    assert expected_apps == NODL_APPS


def test_nodl_subpackages_import() -> None:
    """Test that all nodl subpackages can be imported."""
    import nodl.api
    import nodl.auth
    import nodl.extensions
    import nodl.storage
    import nodl.sync

    assert nodl.auth is not None
    assert nodl.sync is not None
    assert nodl.extensions is not None
    assert nodl.storage is not None
    assert nodl.api is not None
