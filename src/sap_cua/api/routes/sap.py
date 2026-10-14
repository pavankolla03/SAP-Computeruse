"""Local DEV setup. Submitted credentials remain only in server memory."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from sap_cua.runtime.sap_api.connection import ProbeBusy
from sap_cua.runtime.sap_api.profiles import ProfileInput

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


@router.get("/profile")
def profile(request: Request):
    return request.app.state.sap.status()


def require_engineer(request):
    if request.app.state.scope.role == "viewer":
        raise HTTPException(403, "Viewer cannot change the connection")


@router.post("/profile")
def configure(payload: ProfileInput, request: Request):
    require_engineer(request)
    try:
        return request.app.state.sap.configure(payload)
    except ProbeBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            422, "Enter new credentials when changing an API or OAuth endpoint"
        ) from exc


@router.post("/profile/clear")
def clear(payload: ProbeRequest, request: Request):
    require_engineer(request)
    try:
        return request.app.state.sap.clear()
    except ProbeBusy as exc:
        raise HTTPException(409, str(exc)) from exc
