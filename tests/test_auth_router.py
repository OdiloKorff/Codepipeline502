
from importlib import reload

def test_router_prefix():
    module = reload(__import__("product.api.auth_router"))
    router = module.router
    assert router.prefix == "/auth"
