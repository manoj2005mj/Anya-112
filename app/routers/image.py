import tempfile

from fastapi import APIRouter, File, UploadFile

from app.services.gemini import get_image_analysis

router = APIRouter(prefix="/image", tags=["image"])


@router.post("/")
async def image_endpoint(file: UploadFile = File(...)):
    suffix = f"_{file.filename}" if file.filename else ""
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp.flush()
            return await get_image_analysis(tmp.name)
    except Exception:
        return {"text": "Failed to process the image. Please try again.", "error": True}
