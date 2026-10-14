"""Session-authenticated APIs for approved-template SAP DEV jobs."""

import hashlib
import json
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from sap_cua.engineering.live import MAX_ARCHIVE, LivePlanRequest
from sap_cua.security import sanitize_data

router = APIRouter()


def service(request):
    return request.app.state.live


@contextmanager
def errors():
    try:
        yield
    except KeyError as exc:
        raise HTTPException(404, "Live template or run not found") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/status")
def status(request: Request):
    return service(request).status()


@router.get("/templates")
def templates(request: Request):
    return service(request).templates()


@router.post("/templates", status_code=201)
async def import_template(
    request: Request,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    approved: Annotated[bool, Form()],
):
    try:
        archive = await file.read(MAX_ARCHIVE + 1)
    finally:
        await file.close()
    with errors():
        return service(request).import_template(archive, title, approved=approved)


@router.get("/templates/{id}/artifact")
def template_artifact(id: str, request: Request):
    with errors():
        archive = service(request).template_artifact(id)
    return Response(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="approved-template.zip"'},
    )


@router.post("/plans", status_code=201)
def create_plan(payload: LivePlanRequest, request: Request):
    with errors():
        return service(request).create_plan(payload)


@router.get("/plans/{id}")
def get_plan(id: str, request: Request):
    with errors():
        return service(request).get_run(id)["plan"]


@router.get("/plans/{id}/artifact")
def plan_artifact(id: str, request: Request):
    with errors():
        archive = service(request).plan_artifact(id)
    return Response(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="rendered-iflow.zip"'},
    )


@router.post("/plans/{id}/run", status_code=202)
def start_run(id: str, request: Request):
    with errors():
        return service(request).start_run(id)


@router.get("/runs")
def runs(request: Request):
    return service(request).runs()


@router.get("/runs/{id}")
def get_run(id: str, request: Request):
    with errors():
        return service(request).get_run(id)


@router.post("/runs/{id}/cancel")
def cancel_run(id: str, request: Request):
    with errors():
        return service(request).cancel(id)


@router.get("/runs/{id}/export")
def export_run(id: str, request: Request):
    record = get_run(id, request)
    filename = "sap-live-run-" + hashlib.sha256(id.encode()).hexdigest()[:12] + ".json"
    return Response(
        json.dumps(sanitize_data(record), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
