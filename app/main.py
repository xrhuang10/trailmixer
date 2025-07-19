import os
import json
import uuid
import datetime
import random
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
    VideoUploadResponse, JobStatusResponse, SentimentResultResponse, ProcessedVideoResponse, JobListResponse,
    AudioLibrary, AudioSelection, VideoSegmentWithAudio, EnhancedSentimentAnalysisData, AudioPickingRequest,
    FfmpegRequest, InputSegment, VideoCodec, AudioCodec,
    MultiVideoUploadResponse, VideoAnalysisResult, MultiVideoJobInfo, MultiVideoFFmpegRequest
)

app = FastAPI(title="TrailMixer Video Processing API")

# Serve static files for processed videos
app.mount("/static", StaticFiles(directory="../processed_videos"), name="static")

# In-memory storage for job status (in production, use Redis or database)
job_status: Dict[str, JobInfo] = {}
multi_video_job_status: Dict[str, MultiVideoJobInfo] = {}

# Helper function to convert seconds to HH:MM:SS format
def seconds_to_time_format(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

# Audio selection logic
def select_audio_for_segment(segment: VideoSegment, audio_library: AudioLibrary) -> AudioSelection:
    """Select appropriate audio file based on segment sentiment and music style"""
    
    # Map sentiment to audio categories
    sentiment_lower = segment.sentiment.lower()
    music_style_lower = segment.music_style.lower()
    intensity_lower = segment.intensity.lower()
    
    # Determine audio files based on sentiment and style
    if any(word in sentiment_lower for word in ['positive', 'happy', 'joy', 'excited']):
        audio_files = audio_library.happy_files
    elif any(word in sentiment_lower for word in ['negative', 'sad', 'melancholy', 'tragic']):
        audio_files = audio_library.sad_files
    elif any(word in music_style_lower for word in ['energetic', 'upbeat', 'electronic', 'rock']):
        audio_files = audio_library.energetic_files
    elif any(word in music_style_lower for word in ['calm', 'ambient', 'acoustic', 'peaceful']):
        audio_files = audio_library.calm_files
    else:
        audio_files = audio_library.neutral_files
    
    # Select a random file from the appropriate category
    selected_file = random.choice(audio_files)
    
    # Determine volume based on intensity
    if intensity_lower == 'high':
        volume = 0.5
        fade_duration = "0.2"
    elif intensity_lower == 'medium':
        volume = 0.3
        fade_duration = "0.5"
    else:  # low
        volume = 0.2
        fade_duration = "1.0"
    
    return AudioSelection(
        audio_file=selected_file,
        volume=volume,
        fade_in=fade_duration,
        fade_out=fade_duration
    )

def pick_audio(sentiment_data: SentimentAnalysisData, audio_library: Optional[AudioLibrary] = None) -> List[VideoSegmentWithAudio]:
    """
    Pick audio tracks for video segments based on sentiment analysis
    Returns segments with audio selections attached
    """
    print(f"🎵 Starting audio selection for video: {sentiment_data.video_title}")
    
    # Use default audio library if none provided
    if audio_library is None:
        audio_library = AudioLibrary()
    
    segments_with_audio = []
    
    # Process each sentiment-based segment and select appropriate audio
    for i, segment in enumerate(sentiment_data.segments):
        print(f"🎼 Processing segment {i+1}: {segment.sentiment} ({segment.music_style}, {segment.intensity})")
        
        # Select audio for this segment
        audio_selection = select_audio_for_segment(segment, audio_library)
        
        # Create enhanced segment with audio selection
        segment_with_audio = VideoSegmentWithAudio(
            start_time=segment.start_time,
            end_time=segment.end_time,
            sentiment=segment.sentiment,
            music_style=segment.music_style,
            intensity=segment.intensity,
            audio_selection=audio_selection
        )
        
        segments_with_audio.append(segment_with_audio)
        
        print(f"🎵 Selected audio: {audio_selection.audio_file} (vol: {audio_selection.volume:.2f})")
    
    print(f"✅ Audio selection complete! Selected music for {len(segments_with_audio)} segments")
    return segments_with_audio

def create_ffmpeg_request(
    original_video_path: str,
    output_video_path: str,
    video_length: float,
    segments_with_audio: List[VideoSegmentWithAudio],
    global_volume: float = 0.3,
    crossfade_duration: str = "1.0"
) -> FfmpegRequest:
    """
    Create FFmpeg request from video file and segments with audio selections
    """
    print(f"🎬 Creating FFmpeg request for: {original_video_path}")
    
    input_segments = []
    
    # Add the original video as the base track
    video_segment = InputSegment(
        file_path=original_video_path,
        file_type="video",
        start_time="00:00:00",
        end_time=seconds_to_time_format(video_length),
        clip_start="00:00:00",
        clip_end=None,  # Use full video
        volume=1.0,  # Keep original video audio at full volume
        fade_in=None,
        fade_out=None,
        metadata={"type": "original_video"}
    )
    input_segments.append(video_segment)
    
    print(f"📹 Added video track: {video_segment.file_path} (0s - {video_length}s)")
    
    # Add audio tracks for each segment with selected music
    for i, segment in enumerate(segments_with_audio):
        if segment.audio_selection:
            audio_input = InputSegment(
                file_path=segment.audio_selection.audio_file,
                file_type="audio",
                start_time=seconds_to_time_format(segment.start_time),
                end_time=seconds_to_time_format(segment.end_time),
                clip_start="00:00:00",  # Start from beginning of audio file
                clip_end=None,  # Let FFmpeg loop if needed
                volume=segment.audio_selection.volume * global_volume,
                fade_in=segment.audio_selection.fade_in,
                fade_out=segment.audio_selection.fade_out,
                metadata={
                    "type": "background_music",
                    "segment_index": i,
                    "sentiment": segment.sentiment,
                    "music_style": segment.music_style,
                    "intensity": segment.intensity
                }
            )
            input_segments.append(audio_input)
            
            print(f"🎵 Added audio: {segment.audio_selection.audio_file} (vol: {audio_input.volume:.2f})")
    
    # Create the FFmpeg request
    ffmpeg_request = FfmpegRequest(
        input_segments=input_segments,
        output_file=output_video_path,
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        video_bitrate=None,
        audio_bitrate=None,
        crf=23,  # Good quality
        preset="medium",
        scale=None,
        fps=None,
        audio_channels=2,
        audio_sample_rate=44100,
        global_volume=1.0,  # Already applied to individual segments
        normalize_audio=True,
        crossfade_duration=crossfade_duration,
        gap_duration="00:00:00",
        overwrite=True,
        quiet=False,
        progress=True,
        request_id=str(uuid.uuid4()),
        priority=5
    )
    
    print(f"✅ Created FFmpeg request with {len(input_segments)} segments")
    print(f"📁 Output will be saved to: {output_video_path}")
    
    return ffmpeg_request

def create_multi_video_ffmpeg_request(request: MultiVideoFFmpegRequest) -> FfmpegRequest:
    """
    Create FFmpeg request from multiple videos with their audio selections
    Videos will be concatenated in sequence with their respective background music
    """
    print(f"🎬 Creating multi-video FFmpeg request for {len(request.video_results)} videos")
    
    input_segments = []
    current_time_offset = 0.0
    
    for video_idx, video_result in enumerate(request.video_results):
        if not video_result.success or not video_result.sentiment_analysis:
            print(f"⚠️ Skipping video {video_idx + 1} due to processing errors")
            continue
        
        sentiment_data = video_result.sentiment_analysis.sentiment_analysis
        if not isinstance(sentiment_data, SentimentAnalysisData):
            print(f"⚠️ Skipping video {video_idx + 1} due to invalid sentiment data")
            continue
        
        video_length = video_result.video_length or sentiment_data.video_length
        
        print(f"📹 Adding video {video_idx + 1}: {video_result.filename} (duration: {video_length}s)")
        
        # Add video segment with time offset
        video_segment = InputSegment(
            file_path=video_result.file_path,
            file_type="video",
            start_time=seconds_to_time_format(current_time_offset),
            end_time=seconds_to_time_format(current_time_offset + video_length),
            clip_start="00:00:00",
            clip_end=None,
            volume=1.0,
            fade_in=None,
            fade_out=None,
            metadata={
                "type": "video_segment",
                "video_index": video_idx,
                "original_filename": video_result.filename
            }
        )
        input_segments.append(video_segment)
        
        # Add audio segments for this video with time offset
        if video_result.segments_with_audio:
            for audio_segment in video_result.segments_with_audio:
                if audio_segment.audio_selection:
                    audio_input = InputSegment(
                        file_path=audio_segment.audio_selection.audio_file,
                        file_type="audio",
                        start_time=seconds_to_time_format(current_time_offset + audio_segment.start_time),
                        end_time=seconds_to_time_format(current_time_offset + audio_segment.end_time),
                        clip_start="00:00:00",
                        clip_end=None,
                        volume=audio_segment.audio_selection.volume * request.global_volume,
                        fade_in=audio_segment.audio_selection.fade_in,
                        fade_out=audio_segment.audio_selection.fade_out,
                        metadata={
                            "type": "background_music",
                            "video_index": video_idx,
                            "segment_sentiment": audio_segment.sentiment,
                            "music_style": audio_segment.music_style,
                            "intensity": audio_segment.intensity
                        }
                    )
                    input_segments.append(audio_input)
                    
                    print(f"🎵 Added audio for video {video_idx + 1}: {audio_segment.audio_selection.audio_file}")
        
        # Update time offset for next video (add transition time)
        current_time_offset += video_length + float(request.video_transition_duration)
    
    # Create the aggregated FFmpeg request
    ffmpeg_request = FfmpegRequest(
        input_segments=input_segments,
        output_file=request.output_video_path,
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        video_bitrate=None,
        audio_bitrate=None,
        crf=23,
        preset="medium",
        scale=None,
        fps=None,
        audio_channels=2,
        audio_sample_rate=44100,
        global_volume=1.0,
        normalize_audio=True,
        crossfade_duration=request.crossfade_duration,
        gap_duration=request.video_transition_duration,
        overwrite=True,
        quiet=False,
        progress=True,
        request_id=str(uuid.uuid4()),
        priority=5
    )
    
    total_duration = current_time_offset - float(request.video_transition_duration)
    print(f"✅ Created multi-video FFmpeg request:")
    print(f"   📊 Total segments: {len(input_segments)}")
    print(f"   🎬 Videos: {len(request.video_results)}")
    print(f"   ⏱️ Total duration: {total_duration:.1f}s")
    print(f"   📁 Output: {request.output_video_path}")
    
    return ffmpeg_request

def process_single_video_in_batch(video_result: VideoAnalysisResult, audio_library: AudioLibrary) -> VideoAnalysisResult:
    """
    Process a single video within a multi-video batch
    Returns updated VideoAnalysisResult with sentiment analysis and audio selection
    """
    try:
        print(f"🎯 Processing video {video_result.video_index + 1}: {video_result.filename}")
        
        # Step 1: Upload to Twelve Labs
        video_id = upload_video_to_twelvelabs(video_result.file_path)
        if not video_id:
            raise RuntimeError("Failed to upload video to Twelve Labs")
        
        video_result.twelve_labs_video_id = video_id
        print(f"✅ Uploaded to Twelve Labs with ID: {video_id}")
        
        # Step 2: Sentiment analysis
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed: {sentiment_result.error_message}")
        
        video_result.sentiment_analysis = sentiment_result
        
        # Step 3: Audio selection
        if isinstance(sentiment_result.sentiment_analysis, SentimentAnalysisData):
            sentiment_data = sentiment_result.sentiment_analysis
            video_result.video_length = sentiment_data.video_length
            
            segments_with_audio = pick_audio(sentiment_data, audio_library)
            video_result.segments_with_audio = segments_with_audio
            
            print(f"🎵 Selected audio for {len(segments_with_audio)} segments")
        
        video_result.success = True
        return video_result
        
    except Exception as e:
        print(f"❌ Error processing video {video_result.video_index + 1}: {str(e)}")
        video_result.success = False
        video_result.error_message = str(e)
        return video_result

# Background processing function for multiple videos
def process_multi_video_pipeline(job_id: str):
    """Complete multi-video processing pipeline"""
    try:
        job = multi_video_job_status[job_id]
        
        # Step 1: Process each video individually
        job.status = JobStatus.INDEXING
        job.message = f"Processing {job.video_count} videos - indexing and analyzing..."
        
        audio_library = AudioLibrary()
        
        for i, video_file in enumerate(job.video_files):
            job.message = f"Processing video {i+1}/{job.video_count}: indexing and analyzing..."
            
            # Create video result entry
            video_result = VideoAnalysisResult(
                video_index=i,
                filename=video_file,
                file_path=os.path.join("uploads", f"{job_id}_{video_file}"),
                twelve_labs_video_id=None,
                sentiment_analysis=None,
                segments_with_audio=None,
                video_length=None,
                success=False,
                error_message=None
            )
            
            # Process this video
            processed_result = process_single_video_in_batch(video_result, audio_library)
            job.video_results.append(processed_result)
        
        # Step 2: Aggregate all videos into single FFmpeg request
        job.status = JobStatus.PROCESSING
        job.message = "Creating aggregated video with background music..."
        
        output_path = f'../processed_videos/{job_id}_multi_video.mp4'
        
        multi_video_request = MultiVideoFFmpegRequest(
            video_results=job.video_results,
            output_video_path=output_path,
            global_volume=0.3,
            crossfade_duration="1.0",
            video_transition_duration="0.5"
        )
        
        aggregated_ffmpeg_request = create_multi_video_ffmpeg_request(multi_video_request)
        job.aggregated_ffmpeg_request = aggregated_ffmpeg_request.dict()
        
        # TODO: Execute the aggregated FFmpeg request
        print(f"🎬 Multi-video FFmpeg request ready for execution!")
        print(f"   Total input segments: {len(aggregated_ffmpeg_request.input_segments)}")
        
        # Step 3: Complete
        job.status = JobStatus.COMPLETED
        job.message = f"Multi-video processing completed - {job.video_count} videos with background music ready"
        
    except Exception as e:
        multi_video_job_status[job_id].status = JobStatus.FAILED
        multi_video_job_status[job_id].message = f"Multi-video processing failed: {str(e)}"
        print(f"Multi-video pipeline error for job {job_id}: {str(e)}")

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
        
        print(f"🎬 Starting video processing for job: {request.job_id}")
        print(f"📁 Input: {request.file_path}")
        print(f"📁 Output: {output_path}")
        
        # Create audio picking request
        audio_request = AudioPickingRequest(
            sentiment_data=request.sentiment_data,
            original_video_path=request.file_path,
            output_video_path=output_path,
            audio_library=AudioLibrary(),  # Use default audio library
            global_volume=0.3,  # Background music at 30% volume
            crossfade_duration="1.0"  # 1 second crossfade between segments
        )
        
        # Pick audio tracks based on sentiment analysis
        segments_with_audio = pick_audio(audio_request.sentiment_data, audio_request.audio_library)
        
        print(f"🎵 Audio selection complete!")
        print(f"📊 FFmpeg request created with {len(segments_with_audio)} segments")
        
        # Create the FFmpeg request
        ffmpeg_request = create_ffmpeg_request(
            original_video_path=audio_request.original_video_path,
            output_video_path=output_path,
            video_length=audio_request.sentiment_data.video_length,
            segments_with_audio=segments_with_audio,
            global_volume=audio_request.global_volume,
            crossfade_duration=audio_request.crossfade_duration
        )
        
        # TODO: Actually execute the FFmpeg request
        # For now, we'll just log what would be processed
        print("🎬 FFmpeg processing (placeholder):")
        for i, segment in enumerate(ffmpeg_request.input_segments):
            print(f"  Segment {i+1}: {segment.file_type} - {segment.file_path}")
            print(f"    Time: {segment.start_time} -> {segment.end_time}")
            if segment.file_type == "audio":
                print(f"    Volume: {segment.volume:.2f}, Fade: {segment.fade_in}/{segment.fade_out}")
        
        # Process the video with the generated FFmpeg request
        # process_video_with_sentiment(processing_request)  # Old approach
        
        # Calculate actual duration from segments
        max_end_time = max(seg.end_time for seg in request.sentiment_data.segments)
        duration = seconds_to_time_format(max_end_time)
        
        return VideoProcessingResult(
            output_path=output_path,
            segments=request.sentiment_data.segments,
            duration=duration,
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
        
        # Step 3: Select background audio based on sentiment analysis
        job_status[job_id].status = JobStatus.PROCESSING
        job_status[job_id].message = "Selecting background music based on video sentiment..."
        
        ffmpeg_request = None
        if isinstance(sentiment_result.sentiment_analysis, SentimentAnalysisData):
            # Create audio picking request
            output_path = f'../processed_videos/{job_id}_processed.mp4'
            audio_request = AudioPickingRequest(
                sentiment_data=sentiment_result.sentiment_analysis,
                original_video_path=file_path,
                output_video_path=output_path,
                audio_library=AudioLibrary(),  # Use default audio library
                global_volume=0.3,  # Background music at 30% volume
                crossfade_duration="1.0"  # 1 second crossfade between segments
            )
            
            # Pick audio tracks based on sentiment analysis
            segments_with_audio = pick_audio(audio_request.sentiment_data, audio_request.audio_library)
            
            # Create the FFmpeg request
            ffmpeg_request = create_ffmpeg_request(
                original_video_path=audio_request.original_video_path,
                output_video_path=output_path,
                video_length=audio_request.sentiment_data.video_length,
                segments_with_audio=segments_with_audio,
                global_volume=audio_request.global_volume,
                crossfade_duration=audio_request.crossfade_duration
            )
            print(f"🎵 Audio selection complete! Created FFmpeg request with {len(segments_with_audio)} segments")
        
        print("==== FFmpeg Request ====")
        if ffmpeg_request:
            print(ffmpeg_request.input_segments)
        else:
            print("No FFmpeg request generated")
        print("========================")
        
        # Step 4: Process video with FFmpeg based on sentiment and audio selection
        job_status[job_id].message = "Processing video with selected background music..."
        
        if isinstance(sentiment_result.sentiment_analysis, SentimentAnalysisData) and ffmpeg_request:
            processing_request = VideoProcessingRequest(
                file_path=file_path,
                sentiment_data=sentiment_result.sentiment_analysis,
                output_path=ffmpeg_request.output_file,  # Use the output path from audio request
                job_id=job_id
            )
            
            # Store the FFmpeg request in the processing context
            # TODO: Pass ffmpeg_request to process_video_segments for actual FFmpeg execution
            processed_result = process_video_segments(processing_request)
            
            # Add FFmpeg request data to the result
            if processed_result.success:
                processed_data = processed_result.dict()
                processed_data["ffmpeg_request"] = ffmpeg_request.dict()
                processed_data["audio_segments_count"] = len([s for s in ffmpeg_request.input_segments if s.file_type == "audio"])
                processed_data["total_segments"] = len(ffmpeg_request.input_segments)
                job_status[job_id].processed_video = processed_data
            else:
                job_status[job_id].processed_video = processed_result.dict()
            
            if not processed_result.success:
                raise RuntimeError(f"Video processing failed: {processed_result.error_message}")
        
        # Step 5: Complete
        job_status[job_id].status = JobStatus.COMPLETED
        job_status[job_id].message = "Video processing with background music completed successfully"
        
    except Exception as e:
        job_status[job_id].status = JobStatus.FAILED
        job_status[job_id].message = f"Processing failed: {str(e)}"
        print(f"Pipeline error for job {job_id}: {str(e)}")

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
        
        file_path = os.path.join(upload_dir, f"{job_id}_{video_file.filename}")
        try:
            with open(file_path, "wb") as buffer:
                content = video_file.file.read()
                buffer.write(content)
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
        background_tasks.add_task(process_video_pipeline, job_id)
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
        background_tasks.add_task(process_multi_video_pipeline, job_id)
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
    
    # Test pick_audio
    # video_id = '687b35cf4e10ac0ab3549c6b'
    # sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
    # sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
    
    # print("="*60)
    # print("🎬 SENTIMENT ANALYSIS RESULT:")
    # print("="*60)
    # print(f"Success: {sentiment_result.success}")
    
    # if sentiment_result.success and isinstance(sentiment_result.sentiment_analysis, SentimentAnalysisData):
    #     sentiment_data = sentiment_result.sentiment_analysis
    #     print(f"Video Title: {sentiment_data.video_title}")
    #     print(f"Video Length: {sentiment_data.video_length}s")
    #     print(f"Overall Mood: {sentiment_data.overall_mood}")
    #     print(f"Number of Segments: {len(sentiment_data.segments)}")
        
    #     print("\n" + "="*60)
    #     print("🎵 TESTING AUDIO PICKING:")
    #     print("="*60)
        
    #     # Create test audio picking request
    #     test_video_path = "videos/test_video.mp4"  # placeholder path
    #     test_output_path = "processed_videos/test_output.mp4"
        
    #     audio_request = AudioPickingRequest(
    #         sentiment_data=sentiment_data,
    #         original_video_path=test_video_path,
    #         output_video_path=test_output_path,
    #         audio_library=AudioLibrary(),  # Use default audio library
    #         global_volume=0.4,  # Background music at 40% volume
    #         crossfade_duration="1.5"  # 1.5 second crossfade
    #     )
        
    #     try:
    #         # Test the pick_audio function
    #         segments_with_audio = pick_audio(audio_request.sentiment_data, audio_request.audio_library)
            
    #         print("\n" + "="*60)
    #         print("✅ AUDIO PICKING RESULTS:")
    #         print("="*60)
    #         print(f"Output file: {test_output_path}")
    #         print(f"Total input segments: {len(segments_with_audio)}")
            
    #         print("\n📋 SEGMENT BREAKDOWN:")
    #         for i, segment in enumerate(segments_with_audio):
    #             print(f"\n  Segment {i+1}: {segment.sentiment.upper()}")
    #             if segment.audio_selection:
    #                 print(f"    File: {segment.audio_selection.audio_file}")
    #                 print(f"    Time: {segment.start_time} → {segment.end_time}")
    #                 print(f"    Volume: {segment.audio_selection.volume:.2f}")
    #                 if segment.audio_selection.fade_in or segment.audio_selection.fade_out:
    #                     print(f"    Fade: In={segment.audio_selection.fade_in}, Out={segment.audio_selection.fade_out}")
    #             else:
    #                 print(f"    No audio selection")
            
    #         print("\n" + "="*60)
    #         print("🎼 AUDIO MAPPING SUMMARY:")
    #         print("="*60)
    #         audio_segments = [s for s in segments_with_audio if s.audio_selection]
    #         for i, audio_seg in enumerate(audio_segments):
    #             print(f"  Audio {i+1}: {audio_seg.sentiment} sentiment")
    #             print(f"    Style: {audio_seg.music_style}")
    #             print(f"    Intensity: {audio_seg.intensity}")
    #             if audio_seg.audio_selection:
    #                 print(f"    File: {audio_seg.audio_selection.audio_file}")
    #                 print(f"    Volume: {audio_seg.audio_selection.volume:.2f}")
    #             print()
            
    #     except Exception as e:
    #         print(f"❌ Error testing pick_audio: {e}")
    #         import traceback
    #         traceback.print_exc()
    
    # else:
    #     print(f"❌ Sentiment analysis failed: {sentiment_result.error_message}")
    
    # exit()