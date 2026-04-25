def test_pygments_installed():
    try:
        import pygments
        assert True
    except ImportError:
        assert False, "Pygments is not installed"
