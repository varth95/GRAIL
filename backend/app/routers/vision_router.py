"""Vision router: garment image analysis and color correction endpoints.

Routes:
  POST  /vision/analyze                      → analyze a garment image
  PATCH /vision/garments/{garment_id}/color  → correct a garment's color

Requirements: 2.1–2.7, 3.3, 3.4
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import GarmentAnalysisResult, GarmentItem
from app.services.vision_service import analyze_garment, correct_color

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/analyze", response_model=GarmentAnalysisResult, summary="Analyze garment image")
async def analyze_garment_endpoint(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> GarmentAnalysisResult:
    """Accept a multipart image upload and return a GarmentAnalysisResult.

    Extracts user_id from JWT claims stored in request.state.user_claims.
    Returns 422 if the image is invalid or the MIME type is unsupported.

    Requirements: 2.1–2.7
    """
    claims = request.state.user_claims
    user_id = uuid.UUID(claims["sub"])

    image_bytes = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    try:
        result = await analyze_garment(image_bytes, mime_type, user_id, db)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return result


class ColorCorrectionRequest(BaseModel):
    color_hex: str


@router.patch(
    "/garments/{garment_id}/color",
    response_model=GarmentItem,
    summary="Correct garment color",
)
async def correct_color_endpoint(
    garment_id: uuid.UUID,
    body: ColorCorrectionRequest,
    db: AsyncSession = Depends(get_db),
) -> GarmentItem:
    """Apply a user-supplied color correction to a garment.

    Returns 422 if color_hex is invalid or the garment is not found.

    Requirements: 3.3, 3.4
    """
    try:
        return await correct_color(garment_id, body.color_hex, db)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
