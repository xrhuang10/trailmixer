from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import uvicorn
import os
import shutil

from models import VideoUploadRequest, VideoUploadResponse, VideoStitchRequest, VideoStitchResponse, VideoProcessRequest, VideoProcessResponse
from twelve_labs import TwelveLabsClient
from paths import UPLOAD_DIR, PROCESSED_DIR, STITCHED_DIR
from video import stitch_videos, crop_video, apply_music

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
async def upload_video(files: List[UploadFile] = File(...)) -> VideoUploadResponse:
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        filenames = []
        for file in files:
            if file.content_type != "video/mp4":
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a valid MP4 file")
            if not file.filename.lower().endswith(".mp4"):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a valid MP4 file")
            filenames.append(file.filename)
            file_location = UPLOAD_DIR / file.filename
            with open(file_location, "wb") as buffer:
                buffer.write(await file.read())
        return VideoUploadResponse(message=f"{len(files)} MP4 files uploaded successfully", status="success", filenames=filenames)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/video/stitch')
async def stitch_video(request: VideoStitchRequest) -> VideoStitchResponse:
    filenames = request.filenames
    
    if len(filenames) == 1:
        # Move the single file to the stitched directory
        source_file = UPLOAD_DIR / filenames[0]
        dest_file = STITCHED_DIR / filenames[0]
        
        # Ensure the stitched directory exists
        STITCHED_DIR.mkdir(exist_ok=True)
        
        # Move the file
        shutil.move(str(source_file), str(dest_file))
        
        return VideoStitchResponse(message=f"Single file moved to stitched directory", status="success", filename=filenames[0])
    
    try:
        # Process the files
        stitched_filename = stitch_videos(filenames)
        return VideoStitchResponse(message=f"{len(filenames)} MP4 files stitched successfully", status="success", filename=stitched_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get('/api/video/process')
async def process_video(request: VideoProcessRequest) -> VideoProcessResponse:
    filename = request.filename
    music_style = request.music_style
    num_sentiments = request.num_sentiments
    num_segments = request.num_segments
    desired_duration = request.desired_duration
    if filename is None:
        return VideoProcessResponse(message="No filename provided", status="error", filename="")
    
    try:
        # Twelve Labs environment variables
        TWELVE_LABS_API_KEY = os.getenv("TWELVE_LABS_API_KEY")
        TWELVE_LABS_INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")
        if not TWELVE_LABS_API_KEY:
            raise HTTPException(status_code=500, detail="TWELVE_LABS_API_KEY must be set")
        if not TWELVE_LABS_INDEX_ID:
            raise HTTPException(status_code=500, detail="TWELVE_LABS_INDEX_ID must be set")
        
        # Initialize the Twelve Labs client
        twelve_labs_client = TwelveLabsClient(api_key=TWELVE_LABS_API_KEY, index=TWELVE_LABS_INDEX_ID)
                
        # Get the video id
        video_id = twelve_labs_client.upload_video(filename)
        
        # Get the video segments
        segments = twelve_labs_client.prompt_segment(video_id, desired_duration=desired_duration, num_segments=num_segments)
        
        # Crop the video
        cropped_video = crop_video(filename, segments)
        
        # Get the sentiment of the video
        sentiment_segments = twelve_labs_client.prompt_sentiment(video_id, num_sentiments=num_sentiments, music_style=music_style)
        
        # Apply the music
        processed_video = apply_music(cropped_video, sentiment_segments, 'processed.mp4')
        
        # Return the processed video
        return VideoProcessResponse(message="Video processed successfully", status="success", filename=processed_video)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")