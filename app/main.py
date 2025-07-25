from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import uvicorn

from models import VideoUploadRequest, VideoUploadResponse, VideoStitchRequest, VideoStitchResponse
from paths import UPLOAD_DIR, PROCESSED_DIR
from video import stitch_videos

app = FastAPI(title="TrailMixer Video Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],                      # Allow all HTTP methods
    allow_headers=["*"],                      # Allow all headers
)

# Serve the output directory
app.mount("/processed", StaticFiles(directory=PROCESSED_DIR), name="processed")

# Routes
@app.post('/api/video/upload')
async def upload_video(request: VideoUploadRequest) -> VideoUploadResponse:
    files = request.files
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        for file in files:
            if file.content_type != "video/mp4":
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a valid MP4 file")
            if not file.filename.endswith(".mp4"):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a valid MP4 file")
        
        # Save the files to the output directory
        filenames = []
        for file in files:
            filenames.append(file.filename)
            file_location = UPLOAD_DIR / file.filename
            with open(file_location, "wb") as buffer:
                buffer.write(await file.read())
        
        # Process the files
        return VideoUploadResponse(message=f"{len(files)} MP4 files uploaded successfully", status="success", filenames=filenames)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/video/stitch')
async def stitch_video(request: VideoStitchRequest) -> VideoStitchResponse:
    filenames = request.filenames
    if filenames is None or len(filenames) == 0:
        return VideoStitchResponse(message="No files uploaded", status="error", filename="")
    
    if len(filenames) == 1:
        return VideoStitchResponse(message=f"Only one file uploaded, no stitching required", status="success", filename=filenames[0])
    
    try:
        # Process the files
        return VideoStitchResponse(message=f"{len(filenames)} MP4 files stitched successfully", status="success", filename=filenames[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)