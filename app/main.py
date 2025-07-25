from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import uvicorn
import os
from pathlib import Path

app = FastAPI(title="TrailMixer Video Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],                      # Allow all HTTP methods
    allow_headers=["*"],                      # Allow all headers
)

# Serve the output directory
app.mount("/output", StaticFiles(directory="output"), name="output")

# Define absolute path to the output directory
TRAILMIXER_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = TRAILMIXER_ROOT / "upload"
UPLOAD_DIR.mkdir(exist_ok=True)

def is_mp4_file(file: UploadFile) -> bool:
    """Validate if the uploaded file is an MP4 video file."""
    # Check MIME type
    if file.content_type == "video/mp4":
        return True
    
    # Check file extension as fallback
    if file.filename and file.filename.lower().endswith('.mp4'):
        return True
    
    return False

# Routes
@app.post('/api/video/upload')
async def upload_video(files: List[UploadFile] = File(...)):
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        for file in files:
            if file.content_type != "video/mp4":
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a valid MP4 file")
            if not file.filename.endswith(".mp4"):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a valid MP4 file")
        
        # Save the files to the output directory
        for file in files:
            file_location = UPLOAD_DIR / file.filename
            with open(file_location, "wb") as buffer:
                buffer.write(await file.read())
        
        # Process the files
        return {"message": f"{len(files)} MP4 files uploaded successfully", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)