import os
import json
import uuid
import datetime
from typing import Dict, Optional, List
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Import helper functions (to be implemented)
from twelvelabs_client import upload_video_to_twelvelabs, prompt_twelvelabs, clean_llm_string_output_to_json, export_to_json_file
from prompts.extract_info import extract_info_prompt

# Import models
from models import (
    VideoSegment, SentimentAnalysisData, SentimentAnalysisRequest, SentimentAnalysisResponse,
    JobStatus, JobInfo, VideoProcessingRequest, VideoProcessingResult,
    VideoUploadResponse, JobStatusResponse, SentimentResultResponse, ProcessedVideoResponse, JobListResponse
)

app = FastAPI(title="TrailMixer Video Processing API")

# Serve static files for processed videos
app.mount("/static", StaticFiles(directory="../processed_videos"), name="static")

# In-memory storage for job status (in production, use Redis or database)
job_status: Dict[str, JobInfo] = {}

# Helper function placeholders (implement actual logic in separate files)
def extract_segments(file_path: str) -> List[VideoSegment]:
    """Extract video segments from sentiment analysis data"""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        
        # Parse the JSON data into SentimentAnalysisData model for validation
        sentiment_data = SentimentAnalysisData(**data)
        return sentiment_data.segments
    except Exception as e:
        print(f"Error extracting segments from {file_path}: {e}")
        return []

def process_video_with_sentiment(request: VideoProcessingRequest) -> None:
    """Process video with FFmpeg based on sentiment analysis"""
    # TODO: Implement FFmpeg video processing based on sentiment analysis
    # TODO: Use sentiment timestamps to create video segments
    # TODO: Apply different filters/effects based on emotional content
    # TODO: Stitch segments together with transitions
    # TODO: Generate final processed video at request.output_path
    print(f"Processing video: {request.file_path} -> {request.output_path}")
    print(f"Job ID: {request.job_id}")
    print(f"Number of segments: {len(request.sentiment_data.segments)}")
    
    # Placeholder implementation
    pass

def analyze_sentiment_with_twelvelabs(request: SentimentAnalysisRequest) -> SentimentAnalysisResponse:
    """Helper function to analyze sentiment using Twelve Labs"""
    try:
        print(f"Starting sentiment analysis for video ID: {request.video_id}")
        response = prompt_twelvelabs(request.video_id, request.prompt or extract_info_prompt)
        
        if response and hasattr(response, 'data'):
            print(f"Sentiment analysis completed successfully!")
            cleaned_json = clean_llm_string_output_to_json(response.data)
            print(f"Cleaned JSON: {cleaned_json}")
            
            # Validate the JSON structure
            try:
                sentiment_data = SentimentAnalysisData(**cleaned_json)
            except Exception as validation_error:
                print(f"Validation error: {validation_error}")
                return SentimentAnalysisResponse(
                    sentiment_analysis=f"Invalid data format: {validation_error}",
                    file_path=None,
                    success=False,
                    error_message=str(validation_error)
                )
            
            # Use timestamp_video_id format instead of video title to avoid special characters
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            exported_file = export_to_json_file(cleaned_json, f"{timestamp}_{request.video_id}.json")
            
            if exported_file:
                print(f"📁 File saved to: {exported_file}")
            
            return SentimentAnalysisResponse(
                sentiment_analysis=sentiment_data,
                file_path=exported_file,
                success=True,
                error_message=None
            )
        else:
            print(f"No data received from Twelve Labs")
            return SentimentAnalysisResponse(
                sentiment_analysis="No analysis data received",
                file_path=None,
                success=False,
                error_message="No data received from Twelve Labs"
            )
            
    except Exception as e:
        print(f"Error during sentiment analysis: {str(e)}")
        return SentimentAnalysisResponse(
            sentiment_analysis=f"Analysis failed: {str(e)}",
            file_path=None,
            success=False,
            error_message=str(e)
        )

def process_video_segments(request: VideoProcessingRequest) -> VideoProcessingResult:
    """Helper function to process video with FFmpeg based on sentiment"""
    try:
        # This would call your FFmpeg processing logic
        output_path = f'../processed_videos/{request.job_id}_processed.mp4'
        
        # Update the request with the actual output path
        processing_request = VideoProcessingRequest(
            file_path=request.file_path,
            sentiment_data=request.sentiment_data,
            output_path=output_path,
            job_id=request.job_id
        )
        
        # Process the video
        process_video_with_sentiment(processing_request)
        
        return VideoProcessingResult(
            output_path=output_path,
            segments=request.sentiment_data.segments,
            duration="00:05:30",  # placeholder - should calculate actual duration
            success=True,
            error_message=None
        )
    except Exception as e:
        print(f"Error processing video segments: {e}")
        return VideoProcessingResult(
            output_path="",
            segments=[],
            duration="00:00:00",
            success=False,
            error_message=str(e)
        )

# Background processing function
def process_video_pipeline(job_id: str):
    """Complete video processing pipeline"""
    try:
        # Step 1: Upload to Twelve Labs for indexing
        job_status[job_id].status = JobStatus.INDEXING
        job_status[job_id].message = "Uploading video to Twelve Labs for AI analysis..."
        
        file_path = job_status[job_id].file_path
        video_id = upload_video_to_twelvelabs(file_path)
        
        if not video_id:
            raise RuntimeError("Failed to upload video to Twelve Labs")
        
        job_status[job_id].twelve_labs_video_id = video_id
        job_status[job_id].status = JobStatus.ANALYZING
        job_status[job_id].message = "Analyzing video sentiment with AI..."
        
        # Step 2: Perform sentiment analysis
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        job_status[job_id].sentiment_analysis = sentiment_result
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed: {sentiment_result.error_message}")
        
        job_status[job_id].status = JobStatus.PROCESSING
        job_status[job_id].message = "Processing video based on sentiment analysis..."
        
        # Step 3: Process video with FFmpeg based on sentiment
        if isinstance(sentiment_result.sentiment_analysis, SentimentAnalysisData):
            processing_request = VideoProcessingRequest(
                file_path=file_path,
                sentiment_data=sentiment_result.sentiment_analysis,
                output_path="",  # Will be set in process_video_segments
                job_id=job_id
            )
            
            processed_result = process_video_segments(processing_request)
            job_status[job_id].processed_video = processed_result.dict()
            
            if not processed_result.success:
                raise RuntimeError(f"Video processing failed: {processed_result.error_message}")
        
        # Step 4: Complete
        job_status[job_id].status = JobStatus.COMPLETED
        job_status[job_id].message = "Video processing completed successfully"
        
    except Exception as e:
        job_status[job_id].status = JobStatus.FAILED
        job_status[job_id].message = f"Processing failed: {str(e)}"
        print(f"Pipeline error for job {job_id}: {str(e)}")

# ==================== API ENDPOINTS ====================

# WORKS!!!!
@app.post('/api/video/upload', response_model=VideoUploadResponse)
def upload_video(background_tasks: BackgroundTasks, video_file: UploadFile = File(...)):
    """
    Step 1: Upload video and start the complete processing pipeline
    """
    print(f"Uploading video: {video_file.filename}")
    
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
    
    # Initialize job status with JobInfo model
    job_status[job_id] = JobInfo(
        job_id=job_id,
        status=JobStatus.UPLOADING,
        message="Video uploaded, starting processing pipeline...",
        filename=video_file.filename,
        file_path=file_path,
        created_at=datetime.datetime.now().isoformat(),
        twelve_labs_video_id=None,
        sentiment_analysis=None,
        processed_video=None
    )
    
    # Start complete processing pipeline
    background_tasks.add_task(process_video_pipeline, job_id)
    
    print(f"Processing pipeline started for job {job_id}")
    
    return VideoUploadResponse(
        job_id=job_id,
        status=JobStatus.UPLOADING,
        message="Video uploaded, processing pipeline started"
    )

@app.get('/api/video/status/{job_id}', response_model=JobStatusResponse)
def get_processing_status(job_id: str):
    """
    Get current status of video processing pipeline
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
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