import os
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Import helper functions (to be implemented)
from twelvelabs_client import upload_video_to_twelvelabs, prompt_twelvelabs
from prompts.extract_info import extract_info_prompt

app = FastAPI(title="TrailMixer Video Processing API")

# Serve static files for processed videos
app.mount("/static", StaticFiles(directory="../processed_videos"), name="static")

# In-memory storage for job status (in production, use Redis or database)
job_status: Dict[str, Dict] = {}

# Helper function placeholders (implement actual logic in separate files)
def extract_timestamps(sentiment_data: dict) -> list:
    """Extract timestamps from sentiment analysis data"""
    # TODO: Parse sentiment analysis results from Twelve Labs
    # TODO: Extract emotional moments and their corresponding timestamps
    # TODO: Return list of timestamp objects with start/end times and emotions
    return []

def process_video_with_sentiment(file_path: str, sentiment_data: dict, output_path: str) -> None:
    """Process video with FFmpeg based on sentiment analysis"""
    # TODO: Implement FFmpeg video processing based on sentiment analysis
    # TODO: Use sentiment timestamps to create video segments
    # TODO: Apply different filters/effects based on emotional content
    # TODO: Stitch segments together with transitions
    # TODO: Generate final processed video at output_path
    pass

def analyze_sentiment_with_twelvelabs(video_id: str) -> dict:
    """Helper function to analyze sentiment using Twelve Labs"""
    result = prompt_twelvelabs(video_id, extract_info_prompt)
    return {"sentiment_analysis": result.data if result else "Analysis failed"}

def process_video_segments(file_path: str, sentiment_data: dict, job_id: str) -> dict:
    """Helper function to process video with FFmpeg based on sentiment"""
    # This would call your FFmpeg processing logic
    output_path = f'../processed_videos/{job_id}_processed.mp4'
    timestamps = extract_timestamps(sentiment_data)
    process_video_with_sentiment(file_path, sentiment_data, output_path)
    return {
        "output_path": output_path,
        "timestamps": timestamps,
        "duration": "00:05:30"  # placeholder
    }

# Background processing function
def process_video_pipeline(job_id: str, filename: str):
    """Complete video processing pipeline"""
    try:
        # Step 1: Upload to Twelve Labs for indexing
        job_status[job_id]["status"] = "indexing"
        job_status[job_id]["message"] = "Uploading video to Twelve Labs for AI analysis..."
        
        file_path = job_status[job_id]["file_path"]
        video_id = upload_video_to_twelvelabs(file_path)
        
        if not video_id:
            raise RuntimeError("Failed to upload video to Twelve Labs")
        
        job_status[job_id]["twelve_labs_video_id"] = video_id
        job_status[job_id]["status"] = "analyzing"
        job_status[job_id]["message"] = "Analyzing video sentiment with AI..."
        
        # Step 2: Perform sentiment analysis
        sentiment_result = analyze_sentiment_with_twelvelabs(video_id)
        job_status[job_id]["sentiment_analysis"] = sentiment_result
        
        job_status[job_id]["status"] = "processing"
        job_status[job_id]["message"] = "Processing video based on sentiment analysis..."
        
        # Step 3: Process video with FFmpeg based on sentiment
        processed_result = process_video_segments(file_path, sentiment_result, job_id)
        job_status[job_id]["processed_video"] = processed_result
        
        # Step 4: Complete
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["message"] = "Video processing completed successfully"
        
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["message"] = f"Processing failed: {str(e)}"
        print(f"Pipeline error for job {job_id}: {str(e)}")

# ==================== API ENDPOINTS ====================

@app.post('/api/video/upload')
def upload_video(background_tasks: BackgroundTasks, video_file: UploadFile = File(...)):
    """
    Step 1: Upload video and start the complete processing pipeline
    """
    # Validate file type
    if not video_file.content_type or not video_file.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    if not video_file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create upload directory
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save uploaded file
    file_path = os.path.join(upload_dir, f"{job_id}_{video_file.filename}")
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
        "status": "uploading",
        "message": "Video uploaded, starting processing pipeline...",
        "filename": video_file.filename,
        "file_path": file_path,
        "created_at": "2024-01-01T00:00:00Z"  # In production, use actual timestamp
    }
    
    # Start complete processing pipeline
    background_tasks.add_task(process_video_pipeline, job_id, video_file.filename)
    
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "uploading",
            "message": "Video uploaded, processing pipeline started"
        }
    )

@app.get('/api/video/status/{job_id}')
def get_processing_status(job_id: str):
    """
    Get current status of video processing pipeline
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]

@app.get('/api/video/sentiment/{job_id}')
def get_sentiment_analysis(job_id: str):
    """
    Get sentiment analysis results for a processed video
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job["status"] not in ["analyzing", "processing", "completed"]:
        raise HTTPException(status_code=400, detail="Sentiment analysis not yet available")
    
    sentiment_data = job.get("sentiment_analysis")
    if not sentiment_data:
        raise HTTPException(status_code=404, detail="Sentiment analysis not found")
    
    return {
        "job_id": job_id,
        "sentiment_analysis": sentiment_data,
        "twelve_labs_video_id": job.get("twelve_labs_video_id"),
        "status": job["status"]
    }

@app.post('/api/video/reprocess/{job_id}')
def reprocess_video(job_id: str, background_tasks: BackgroundTasks):
    """
    Manually trigger FFmpeg processing step (if needed to reprocess)
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if "sentiment_analysis" not in job:
        raise HTTPException(status_code=400, detail="No sentiment analysis available for reprocessing")
    
    # Trigger reprocessing
    def reprocess_pipeline(job_id: str):
        try:
            job_status[job_id]["status"] = "processing"
            job_status[job_id]["message"] = "Reprocessing video with FFmpeg..."
            
            file_path = job_status[job_id]["file_path"]
            sentiment_data = job_status[job_id]["sentiment_analysis"]
            
            processed_result = process_video_segments(file_path, sentiment_data, job_id)
            job_status[job_id]["processed_video"] = processed_result
            job_status[job_id]["status"] = "completed"
            job_status[job_id]["message"] = "Video reprocessing completed"
            
        except Exception as e:
            job_status[job_id]["status"] = "failed"
            job_status[job_id]["message"] = f"Reprocessing failed: {str(e)}"
    
    background_tasks.add_task(reprocess_pipeline, job_id)
    
    return {
        "job_id": job_id,
        "message": "Reprocessing started",
        "status": "processing"
    }

@app.get('/api/video/result/{job_id}')
def get_processed_video_info(job_id: str):
    """
    Get information about the processed video including timestamps
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.get("processed_video")
    if not processed_data:
        raise HTTPException(status_code=404, detail="Processed video not found")
    
    return {
        "job_id": job_id,
        "original_filename": job["filename"],
        "processed_video": {
            "download_url": f"/api/video/download/{job_id}",
            "stream_url": f"/api/video/stream/{job_id}",
            "timestamps": processed_data["timestamps"],
            "duration": processed_data["duration"]
        },
        "sentiment_analysis": job.get("sentiment_analysis", {}),
        "twelve_labs_video_id": job.get("twelve_labs_video_id"),
        "status": job["status"]
    }

@app.get('/api/video/download/{job_id}')
def download_processed_video(job_id: str):
    """
    Download the final processed video file
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.get("processed_video")
    if not processed_data or not os.path.exists(processed_data["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        path=processed_data["output_path"],
        media_type='video/mp4',
        filename=f"processed_{job['filename']}"
    )

@app.get('/api/video/stream/{job_id}')
def stream_processed_video(job_id: str):
    """
    Stream the processed video for in-browser playback
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.get("processed_video")
    if not processed_data or not os.path.exists(processed_data["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        path=processed_data["output_path"],
        media_type='video/mp4',
        headers={"Accept-Ranges": "bytes"}
    )

@app.get('/api/jobs')
def list_all_jobs():
    """
    List all processing jobs (for debugging/admin)
    """
    return {
        "jobs": [
            {
                "job_id": job_id,
                "status": job["status"],
                "filename": job["filename"],
                "message": job["message"]
            }
            for job_id, job in job_status.items()
        ]
    }

@app.delete('/api/video/{job_id}')
def delete_job(job_id: str):
    """
    Delete a job and its associated files
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    # Clean up files
    try:
        if os.path.exists(job["file_path"]):
            os.remove(job["file_path"])
        
        processed_data = job.get("processed_video")
        if processed_data and os.path.exists(processed_data["output_path"]):
            os.remove(processed_data["output_path"])
    except Exception as e:
        print(f"Error cleaning up files for job {job_id}: {e}")
    
    # Remove from job status
    del job_status[job_id]
    
    return {"message": f"Job {job_id} deleted successfully"}

# Health check endpoint
@app.get('/health')
def health_check():
    return {"status": "healthy", "service": "TrailMixer Video Processing API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)