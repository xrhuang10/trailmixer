import os
import uuid
import datetime
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from video_processor import convert_mov_to_mp4
# Import models
from models import (
    VideoSegment, SentimentAnalysisData, SentimentAnalysisRequest, SentimentAnalysisResponse,
    JobStatus, JobInfo, VideoProcessingRequest, VideoProcessingResult,
    VideoUploadResponse, JobStatusResponse, SentimentResultResponse, ProcessedVideoResponse, JobListResponse,
    AudioLibrary, AudioSelection, VideoSegmentWithAudio, EnhancedSentimentAnalysisData, AudioPickingRequest,
    FfmpegRequest, InputSegment, VideoCodec, AudioCodec,
    MultiVideoUploadResponse, VideoAnalysisResult, MultiVideoJobInfo, MultiVideoFFmpegRequest
)

# Import processing modules
from pipeline import process_video_pipeline, process_multi_video_pipeline
from video_processor import extract_segments

app = FastAPI(title="TrailMixer Video Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],                      # Allow all HTTP methods
    allow_headers=["*"],                      # Allow all headers
)


# Serve static files for processed videos
app.mount("/static", StaticFiles(directory="../processed_videos"), name="static")

# In-memory storage for job status (in production, use Redis or database)
job_status: Dict[str, JobInfo] = {}
multi_video_job_status: Dict[str, MultiVideoJobInfo] = {}

# ==================== API ENDPOINTS ====================

@app.post('/api/video/upload', response_model=MultiVideoUploadResponse)
def upload_video(background_tasks: BackgroundTasks, video_files: List[UploadFile] = File(...)):
    """
    Upload one or more videos and start the complete processing pipeline
    Handles both single video and multi-video processing automatically
    """
    if not video_files:
        raise HTTPException(status_code=400, detail="No video files provided")
    
    print(f"Uploading {len(video_files)} video(s)")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create upload directory
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save uploaded files
    file_paths = []
    for i, video_file in enumerate(video_files):
        if not video_file.content_type or not video_file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail=f"File {i+1} must be a video")
        if not video_file.filename:
            raise HTTPException(status_code=400, detail=f"Filename for file {i+1} is required")
        
        orig_filename = video_file.filename
        file_path = os.path.join(upload_dir, f"{job_id}_{orig_filename}")
        try:
            with open(file_path, "wb") as buffer:
                content = video_file.file.read()
                buffer.write(content)
            
            # If it's a .mov, convert to .mp4 and use the new path
            if orig_filename.lower().endswith('.mov'):
                try:
                    converted_path = convert_mov_to_mp4(file_path)
                    os.remove(file_path)  # Optional: remove original .mov
                    file_path = converted_path
                    # Also update filename for the rest of the pipeline
                    video_file.filename = os.path.basename(converted_path)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"FFmpeg conversion failed: {str(e)}")
            
            file_paths.append(file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file {i+1}: {str(e)}")
        finally:
            video_file.file.close()

    
    # Choose processing approach based on number of videos
    if len(video_files) == 1:
        # Single video processing (use existing pipeline)
        video_file = video_files[0]
        job_status[job_id] = JobInfo(
            job_id=job_id,
            status=JobStatus.UPLOADING,
            message="Video uploaded, starting processing pipeline...",
            filename=video_file.filename or "unknown.mp4",
            file_path=file_paths[0],
            created_at=datetime.datetime.now().isoformat(),
            twelve_labs_video_id=None,
            sentiment_analysis=None,
            processed_video=None
        )
        
        # Start single video processing pipeline
        background_tasks.add_task(process_video_pipeline, job_id, job_status)
        print(f"Single video processing pipeline started for job {job_id}")
        
        message = "Video uploaded, processing pipeline started"
    else:
        # Multi-video processing
        multi_video_job_status[job_id] = MultiVideoJobInfo(
            job_id=job_id,
            status=JobStatus.UPLOADING,
            message=f"Videos uploaded, starting multi-video processing pipeline for {len(video_files)} videos...",
            filename=f"multi_video_{len(video_files)}_files",
            file_path=upload_dir,
            created_at=datetime.datetime.now().isoformat(),
            twelve_labs_video_id=None,
            sentiment_analysis=None,
            processed_video=None,
            video_count=len(video_files),
            video_files=[f.filename for f in video_files if f.filename],
            video_results=[],
            aggregated_ffmpeg_request=None
        )
        
        # Start multi-video processing pipeline
        background_tasks.add_task(process_multi_video_pipeline, job_id, multi_video_job_status)
        print(f"Multi-video processing pipeline started for job {job_id}")
        
        message = f"Videos uploaded, multi-video processing pipeline started for {len(video_files)} videos"
    
    return MultiVideoUploadResponse(
        job_id=job_id,
        status=JobStatus.UPLOADING,
        message=message,
        video_count=len(video_files),
        video_files=[f.filename for f in video_files if f.filename]
    )

@app.get('/api/video/status/{job_id}', response_model=JobStatusResponse)
def get_processing_status(job_id: str):
    """
    Get current status of video processing pipeline (single or multi-video)
    """
    # Check single video jobs first
    if job_id in job_status:
        job = job_status[job_id]
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            message=job.message,
            filename=job.filename,
            created_at=job.created_at,
            twelve_labs_video_id=job.twelve_labs_video_id,
            progress_percentage=None
        )
    
    # Check multi-video jobs
    elif job_id in multi_video_job_status:
        job = multi_video_job_status[job_id]
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            message=job.message,
            filename=job.filename,
            created_at=job.created_at,
            twelve_labs_video_id=job.twelve_labs_video_id,
            progress_percentage=None
        )
    
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@app.get('/api/video/sentiment/{job_id}', response_model=SentimentResultResponse)
def get_sentiment_analysis(job_id: str):
    """
    Get sentiment analysis results for a processed video
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job.status not in [JobStatus.ANALYZING, JobStatus.PROCESSING, JobStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="Sentiment analysis not yet available")
    
    if not job.sentiment_analysis or not job.sentiment_analysis.success:
        raise HTTPException(status_code=404, detail="Sentiment analysis not found or failed")
    
    if not isinstance(job.sentiment_analysis.sentiment_analysis, SentimentAnalysisData):
        raise HTTPException(status_code=400, detail="Invalid sentiment analysis data")
    
    return SentimentResultResponse(
        job_id=job_id,
        sentiment_analysis=job.sentiment_analysis.sentiment_analysis,
        twelve_labs_video_id=job.twelve_labs_video_id or "",
        status=job.status
    )

@app.post('/api/video/reprocess/{job_id}')
def reprocess_video(job_id: str, background_tasks: BackgroundTasks):
    """
    Manually trigger FFmpeg processing step (if needed to reprocess)
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if not job.sentiment_analysis or not job.sentiment_analysis.success:
        raise HTTPException(status_code=400, detail="No valid sentiment analysis available for reprocessing")
    
    # Trigger reprocessing
    def reprocess_pipeline(job_id: str):
        try:
            job_status[job_id].status = JobStatus.PROCESSING
            job_status[job_id].message = "Reprocessing video with FFmpeg..."
            
            job = job_status[job_id]
            if job.sentiment_analysis and isinstance(job.sentiment_analysis.sentiment_analysis, SentimentAnalysisData):
                # Import here to avoid circular dependency
                from video_processor import process_video_segments
                
                processing_request = VideoProcessingRequest(
                    file_path=job.file_path,
                    sentiment_data=job.sentiment_analysis.sentiment_analysis,
                    output_path="",
                    job_id=job_id
                )
                
                processed_result = process_video_segments(processing_request)
                job_status[job_id].processed_video = processed_result.dict()
                
                if processed_result.success:
                    job_status[job_id].status = JobStatus.COMPLETED
                    job_status[job_id].message = "Video reprocessing completed"
                else:
                    raise RuntimeError(processed_result.error_message or "Unknown processing error")
            
        except Exception as e:
            job_status[job_id].status = JobStatus.FAILED
            job_status[job_id].message = f"Reprocessing failed: {str(e)}"
    
    background_tasks.add_task(reprocess_pipeline, job_id)
    
    return {
        "job_id": job_id,
        "message": "Reprocessing started",
        "status": JobStatus.PROCESSING.value
    }

@app.get('/api/video/result/{job_id}', response_model=ProcessedVideoResponse)
def get_processed_video_info(job_id: str):
    """
    Get information about the processed video including timestamps
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.processed_video
    if not processed_data:
        raise HTTPException(status_code=404, detail="Processed video not found")
    
    # Create processed video info dict
    processed_video_info = {
        "download_url": f"/api/video/download/{job_id}",
        "stream_url": f"/api/video/stream/{job_id}",
        "timestamps": processed_data["segments"],
        "duration": processed_data["duration"]
    }
    
    # Extract sentiment analysis data safely
    sentiment_data = job.sentiment_analysis.sentiment_analysis if job.sentiment_analysis else None
    if not isinstance(sentiment_data, SentimentAnalysisData):
        raise HTTPException(status_code=400, detail="Invalid sentiment analysis data")
    
    return ProcessedVideoResponse(
        job_id=job_id,
        original_filename=job.filename,
        processed_video=processed_video_info,
        sentiment_analysis=sentiment_data,
        twelve_labs_video_id=job.twelve_labs_video_id or "",
        status=job.status
    )

@app.get('/api/video/ffmpeg-request/{job_id}')
def get_ffmpeg_request(job_id: str):
    """
    Get the generated FFmpeg request for a completed video processing job (single or multi-video)
    This can be used by external FFmpeg processing systems
    """
    # Check single video jobs first
    if job_id in job_status:
        job = job_status[job_id]
        
        if job.status not in [JobStatus.PROCESSING, JobStatus.COMPLETED]:
            raise HTTPException(status_code=400, detail="FFmpeg request not yet available")
        
        processed_data = job.processed_video
        if not processed_data:
            raise HTTPException(status_code=404, detail="Processed video data not found")
        
        # The processing data should contain the FFmpeg request
        if "ffmpeg_request" not in processed_data:
            raise HTTPException(status_code=404, detail="FFmpeg request not found in processed data")
        
        return {
            "job_id": job_id,
            "status": job.status.value,
            "ffmpeg_request": processed_data["ffmpeg_request"],
            "total_segments": processed_data.get("total_segments", 0),
            "audio_segments_count": processed_data.get("audio_segments_count", 0),
            "message": "Single video FFmpeg request ready for execution"
        }
    
    # Check multi-video jobs
    elif job_id in multi_video_job_status:
        job = multi_video_job_status[job_id]
        
        if job.status not in [JobStatus.PROCESSING, JobStatus.COMPLETED]:
            raise HTTPException(status_code=400, detail="FFmpeg request not yet available")
        
        if not job.aggregated_ffmpeg_request:
            raise HTTPException(status_code=404, detail="Aggregated FFmpeg request not found")
        
        return {
            "job_id": job_id,
            "status": job.status.value,
            "ffmpeg_request": job.aggregated_ffmpeg_request,
            "total_segments": len(job.aggregated_ffmpeg_request.get("input_segments", [])),
            "video_count": job.video_count,
            "message": "Multi-video aggregated FFmpeg request ready for execution"
        }
    
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@app.get('/api/video/download/{job_id}')
def download_processed_video(job_id: str):
    """
    Download the final processed video file
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.processed_video
    if not processed_data or not os.path.exists(processed_data["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        path=processed_data["output_path"],
        media_type='video/mp4',
        filename=f"processed_{job.filename}"
    )

@app.get('/api/video/stream/{job_id}')
def stream_processed_video(job_id: str):
    """
    Stream the processed video for in-browser playback
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.processed_video
    if not processed_data or not os.path.exists(processed_data["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        path=processed_data["output_path"],
        media_type='video/mp4',
        headers={"Accept-Ranges": "bytes"}
    )

@app.get('/api/jobs', response_model=JobListResponse)
def list_all_jobs():
    """
    List all processing jobs (for debugging/admin)
    """
    return JobListResponse(
        jobs=[
            {
                "job_id": job_id,
                "status": job.status,
                "filename": job.filename,
                "message": job.message
            }
            for job_id, job in job_status.items()
        ]
    )

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
        if os.path.exists(job.file_path):
            os.remove(job.file_path)
        
        processed_data = job.processed_video
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