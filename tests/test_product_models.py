
import pytest
from product.database.models import Project, RefreshToken, User

pytestmark = pytest.mark.db_integration

def test_models_attributes():
    assert hasattr(User, "__tablename__")
    assert hasattr(RefreshToken, "__tablename__")
    assert hasattr(Project, "__tablename__")
