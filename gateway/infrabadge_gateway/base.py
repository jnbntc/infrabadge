from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

DeviceId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")]
Epoch = Annotated[int, Field(ge=1577836800, le=4102444800)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
