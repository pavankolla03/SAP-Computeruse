"""Local connection status and read-only capability probes; no secret input API."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from sap_cua.runtime.sap_api.connection import ProbeBusy

router = APIRouter()


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.get("/status")
def status(request: Request):
    return request.app.state.sap.status()


@router.post("/probe")
def probe(payload: ProbeRequest, request: Request):
    try:
        return request.app.state.sap.probe()
    except ProbeBusy as exc:
        raise HTTPException(409, str(exc)) from exc
