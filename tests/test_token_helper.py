
import importlib
import os

os.environ["JWT_SECRET"] = "testsecret"
import product.security.token as token_mod

importlib.reload(token_mod)
from datetime import timedelta

import jwt
from product.security.token import ALGORITHM, SECRET_KEY, create_access_token


def test_create_access_token():
    token = create_access_token({"sub": "user@example.com"}, expires_delta=timedelta(minutes=5))
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "user@example.com"
