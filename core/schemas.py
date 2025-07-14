from pydantic import BaseModel
from typing import List

class MethodModel(BaseModel):
    name: str

class ClassModel(BaseModel):
    name: str
    methods: List[MethodModel]
    dependencies: List[str] = []

class PlanModel(BaseModel):
    classes: List[ClassModel]