from fastapi import FastAPI
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from com.mhire.app.services.verification_system.face_verification.face_verification_router import router as face_router


app = FastAPI(
    title="Face Recognition Fraud Protection System",
    description="API for face verification and duplicate detection using Face++ and FAISS",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(face_router)


@app.get("/", status_code=status.HTTP_200_OK, response_class=PlainTextResponse)
async def health_check():
    return "Face Recognition Fraud Protection System is running and healthy"
