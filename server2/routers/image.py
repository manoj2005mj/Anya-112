"""
Image router for server2 backend.

Provides the /image endpoint that matches the frontend's expected format.
Compatible with the existing frontend (Dashboard.tsx).
"""

import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from server2.config import get_settings
from server2.logging_utils import ErrorComponent, get_logger
from server2.services.incident_enrichment import enrich_incident_response

logger = get_logger("anya.server2.routers.image")
router = APIRouter(prefix="/image", tags=["image"])


class ImageResponse(BaseModel):
    """Response model for image endpoint matching frontend format"""
    text: str


@router.post("")
async def analyze_image(
    file: UploadFile = File(..., description="Image file to analyze"),
):
    """
    Image analysis endpoint that matches the frontend's expected format.

    Frontend sends multipart/form-data with:
    - file: [binary image data]

    Frontend expects response:
    {
      "text": "AI analysis text with optional JSON block"
    }
    """
    settings = get_settings()

    try:
        logger.info(
            f"Image analysis request received",
            component=ErrorComponent.GEMINI_IMAGE,
            filename=file.filename,
            content_type=file.content_type,
        )

        # Import here to avoid issues if not installed
        from google import genai

        # Initialize Gemini client
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={"api_version": "v1beta"},
        )

        # Save uploaded file temporarily
        temp_file_path = f"/tmp/{file.filename}"
        try:
            # Write uploaded file to temp location
            with open(temp_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            logger.debug(
                f"Image saved to temp file",
                component=ErrorComponent.GEMINI_IMAGE,
                temp_path=temp_file_path,
                file_size=len(content),
            )

            # Upload to Gemini
            upload = client.files.upload(file=temp_file_path)
            if not upload.uri:
                logger.error(
                    f"Failed to upload file to Gemini",
                    component=ErrorComponent.GEMINI_IMAGE,
                    filename=file.filename,
                )
                raise HTTPException(status_code=500, detail="Failed to upload file")

            logger.info(
                f"File uploaded to Gemini successfully",
                component=ErrorComponent.GEMINI_IMAGE,
                file_uri=upload.uri,
            )

            # Generate content with image - use simple content format
            prompt = (
                "Analyze this image for emergency assessment. "
                "Identify any hazards, injuries, or critical details. "
                "At the end, output a JSON block with incident_location, "
                "disaster_type, departments_required, severity, and extracted_entities."
            )

            # Format model name correctly
            model_name = settings.GEMINI_MODEL
            if model_name.startswith("models/"):
                model_name = model_name.replace("models/", "", 1)

            response = client.models.generate_content(
                model=model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"file_data": {"file_uri": upload.uri, "mime_type": upload.mime_type}},
                            {"text": prompt}
                        ]
                    }
                ],
            )

            logger.info(
                f"Image analysis completed successfully",
                component=ErrorComponent.GEMINI_IMAGE,
                response_length=len(response.text) if response.text else 0,
            )

            enriched_text = await enrich_incident_response(
                response.text or "",
                file.filename or "uploaded image",
                history=None,
            )

            return ImageResponse(text=enriched_text)

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.debug(
                    f"Temp file cleaned up",
                    component=ErrorComponent.GEMINI_IMAGE,
                    temp_path=temp_file_path,
                )

    except Exception as e:
        # Enhanced error logging with component identification
        logger.error(
            f"Error in image endpoint: {str(e)}",
            component=ErrorComponent.GEMINI_IMAGE,
            include_traceback=True,
            filename=file.filename if file else "unknown",
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Image analysis failed",
                "component": ErrorComponent.GEMINI_IMAGE.value,
                "message": str(e)
            }
        )
