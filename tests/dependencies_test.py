import importlib.util

def test_pygments_installed():
    assert importlib.util.find_spec("pygments") is not None, "Pygments is not installed"
