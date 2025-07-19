import os
import uuid
from typing import Dict

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from app.twelvelabs_client import upload_video_to_twelvelabs

app = FastAPI()

job_status: Dict[str, Dict] = {}

# Main processing function
def process_video_background(job_id: str, filename: str):
    """
    Background task for video processing pipeline:
    1. Twelve Labs analysis and indexing
    2. FFmpeg operations (placeholder)
    """
    try:
        # Update status to processing
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "Uploading and analyzing video with Twelve Labs..."
        
        # Get file path from job status
        file_path = job_status[job_id]["file_path"]
        
        # Upload to Twelve Labs for indexing
        video_id = upload_video_to_twelvelabs(file_path, filename)
        
        # Update job status with Twelve Labs video ID
        job_status[job_id]["twelve_labs_video_id"] = video_id
        job_status[job_id]["message"] = "Twelve Labs indexing completed. Running FFmpeg operations..."
        
        # TODO: Add actual FFmpeg processing here
        # This is where you would add your FFmpeg video processing logic
        # Example: convert formats, extract thumbnails, etc.
        
        # Mark as completed
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["message"] = "Video processing completed successfully"
        job_status[job_id]["processed_filename"] = f"processed_{filename}"
        
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["message"] = f"Processing failed: {str(e)}"
        print(f"Background processing error for job {job_id}: {str(e)}")

@app.post('/api/video/upload')
def upload_video(background_tasks: BackgroundTasks, video_file: UploadFile = File(...)):
    """
    Upload a video file and initiate background processing.
    
    Returns:
        202 Accepted with job_id for tracking processing status
    """
    
    # Validate file type (basic validation)
    if not video_file.content_type or not video_file.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    # Validate filename exists
    if not video_file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create upload directory if it doesn't exist
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save the uploaded file
    file_path = os.path.join(upload_dir, video_file.filename)
    try:
        with open(file_path, "wb") as buffer:
            content = video_file.file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    finally:
        video_file.file.close()
    
    # Initialize job status
    job_status[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "message": "Video uploaded, processing started.",
        "filename": video_file.filename,
        "file_path": file_path
    }
    
    # Start background processing
    background_tasks.add_task(process_video_background, job_id, video_file.filename)
    
    # Return 202 Accepted with job tracking info
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "processing",
            "message": "Video uploaded, processing started."
        }
    )

@app.get('/api/video/status/{job_id}')
def get_job_status(job_id: str):
    """
    Get the current status of a video processing job.
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]

@app.get('/api/twelvelabs/config')
def get_twelvelabs_config():
    """
    Get Twelve Labs configuration status.
    """
    return {
        "api_key_configured": bool(TWELVE_LABS_API_KEY),
        "index_id_configured": bool(TWELVE_LABS_INDEX_ID), 
        "client_initialized": twelve_labs_client is not None,
        "status": "ready" if (TWELVE_LABS_API_KEY and TWELVE_LABS_INDEX_ID) else "not_configured"
    }

@app.get('/video/processed/{video_filename}')
def get_processed_video(video_filename: str):
    pass