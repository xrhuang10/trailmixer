from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import uvicorn
import os
import shutil
from pathlib import Path

from models import VideoUploadResponse, VideoStitchRequest, VideoStitchResponse, VideoProcessRequest, VideoProcessResponse
from twelve_labs import TwelveLabsClient
from paths import UPLOAD_DIR, PROCESSED_DIR, STITCHED_DIR, CROPPED_DIR, VIDEOS_DIR
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
        source_file = UPLOAD_DIR / filenames[0]
        dest_file = STITCHED_DIR / filenames[0]
        STITCHED_DIR.mkdir(exist_ok=True)
        shutil.move(str(source_file), str(dest_file))
        return VideoStitchResponse(message=f"Single file moved to stitched directory", status="success", filename=filenames[0])
    try:
        file_paths = [UPLOAD_DIR / fname for fname in filenames]
        stitched_path = stitch_videos(file_paths)
        return VideoStitchResponse(message=f"{len(filenames)} MP4 files stitched successfully", status="success", filename=stitched_path.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/video/process')
async def process_video(request: VideoProcessRequest) -> VideoProcessResponse:
    filename = request.filename
    music_style = request.music_style
    num_sentiments = request.num_sentiments
    num_segments = request.num_segments
    desired_duration = request.desired_duration
    
    if filename is None:
        return VideoProcessResponse(message="No filename provided", status="error", filename="")
    
    try:
        # Initialize the Twelve Labs client
        TWELVE_LABS_API_KEY = os.getenv("TWELVE_LABS_API_KEY")
        TWELVE_LABS_INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")
        if not TWELVE_LABS_API_KEY:
            raise HTTPException(status_code=500, detail="TWELVE_LABS_API_KEY must be set")
        if not TWELVE_LABS_INDEX_ID:
            raise HTTPException(status_code=500, detail="TWELVE_LABS_INDEX_ID must be set")
        
        twelve_labs_client = TwelveLabsClient(api_key=TWELVE_LABS_API_KEY, index=TWELVE_LABS_INDEX_ID)
        
        # Upload the original video for segmentation
        video_path = STITCHED_DIR / filename
        video_id = twelve_labs_client.upload_video(video_path)
        
        # Get the video segments
        segments = twelve_labs_client.prompt_segment(video_id, desired_duration=desired_duration, num_segments=num_segments)
        
        # Crop the video
        cropped_path = crop_video(video_path, segments, 'cropped.mp4')
        
        # Upload the cropped video for sentiment analysis
        cropped_video_id = twelve_labs_client.upload_video(cropped_path)
        
        # Get the sentiment of the cropped video
        sentiment_segments = twelve_labs_client.prompt_sentiment(cropped_video_id, num_sentiments=num_sentiments, music_style=music_style)
        
        # Apply the music
        processed_path = apply_music(cropped_path, sentiment_segments)
        
        # Return the processed video
        return VideoProcessResponse(message="Video processed successfully", status="success", filename=processed_path.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
    # import asyncio
    # asyncio.run(process_video(VideoProcessRequest(filename=str(VIDEOS_DIR / "tom_and_jerry_trailer_no_music.mp4"), music_style="meme", num_sentiments=1, num_segments=2, desired_duration=15)))