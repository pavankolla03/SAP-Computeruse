"""Typed arguments for executable V1 actions. Unknown actions fail before writes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Package(Arguments):
    package_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,100}$")
    name: str = Field(min_length=1, max_length=200)


class Flow(Arguments):
    package_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,100}$")
    iflow_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,100}$")


class CreateFlow(Flow):
    name: str = Field(min_length=1, max_length=200)


class Adapter(Flow):
    direction: Literal["sender", "receiver"]
    adapter: Literal["HTTPS", "HTTP", "ODataV2", "ODataV4", "SFTP", "SOAP", "JMS", "EventMesh"]
    config: dict[str, str | None]


class Component(Flow):
    component: Literal["ContentModifier", "Router", "Splitter", "JMSRetry", "ExceptionSubprocess"]
    after: str = Field(min_length=1, max_length=100)


class Test(Flow):
    payload: dict


class Query(Arguments):
    package_id: str | None = None
    iflow_id: str | None = None
    error_class: str | None = None


class Diagnose(Arguments):
    error_class: Literal["401", "429", "timeout"]


ACTIONS = {
    "CREATE_PACKAGE": Package,
    "CREATE_IFLOW": CreateFlow,
    "CONFIGURE_ADAPTER": Adapter,
    "ADD_COMPONENT": Component,
    "SAVE_IFLOW": Flow,
    "DEPLOY_IFLOW": Flow,
    "RUN_TEST": Test,
    "QUERY_MPL": Query,
    "DIAGNOSE_ERROR": Diagnose,
}


def validate_step(step):
    schema = ACTIONS.get(step.action)
    if schema is None:
        raise ValueError("Unsupported semantic action: " + step.action)
    return schema.model_validate(step.args)
