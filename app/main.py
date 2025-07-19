import uuid
import os
from typing import Dict
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

# In-memory storage for job status (in production, use Redis or database)
job_status: Dict[str, Dict] = {}

def process_video_background(job_id: str, filename: str):
    """
    Background task to simulate video processing pipeline:
    1. Twelve Labs analysis
    2. FFmpeg operations
    """
    try:
        # Update status to processing
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "Analyzing video with Twelve Labs..."
        
        # Simulate Twelve Labs analysis (replace with actual API call)
        
        job_status[job_id]["message"] = "Running FFmpeg operations..."
        
        # Simulate FFmpeg processing (replace with actual FFmpeg operations)
        
        # Mark as completed
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["message"] = "Video processing completed successfully"
        job_status[job_id]["processed_filename"] = f"processed_{filename}"
        
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["message"] = f"Processing failed: {str(e)}"

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

@app.get('/video/processed/{video_filename}')
def get_processed_video(video_filename: str):
    pass