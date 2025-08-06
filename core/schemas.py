
from pydantic import BaseModel


class MethodModel(BaseModel):
    name: str

class ClassModel(BaseModel):
    name: str
    methods: list[MethodModel]
    dependencies: list[str] = []

class PlanModel(BaseModel):
    classes: list[ClassModel]
