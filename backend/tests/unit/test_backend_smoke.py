from aimplify_intake import __version__


def test_backend_package_metadata() -> None:
    assert __version__ == "0.1.0"
