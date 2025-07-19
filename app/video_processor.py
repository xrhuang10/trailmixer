"""
Video processing and sentiment analysis utilities
"""
import json
import datetime
import os
from typing import List
from models import (
    VideoSegment, SentimentAnalysisData, SentimentAnalysisRequest, SentimentAnalysisResponse,
    VideoProcessingRequest, VideoProcessingResult, AudioPickingRequest, AudioLibrary,
    VideoAnalysisResult
)

# Import Twelve Labs functions
from twelvelabs_client import upload_video_to_twelvelabs, prompt_twelvelabs, clean_llm_string_output_to_json, export_to_json_file
from prompts.extract_info import extract_info_prompt
from audio_picker import pick_audio
from ffmpeg_builder import create_ffmpeg_request, seconds_to_time_format

def extract_segments(file_path: str) -> List[VideoSegment]:
    """Extract video segments from sentiment analysis data"""
    try:
        filename = os.path.basename(file_path)
        print(f"📄 Extracting segments from: {filename}")
        
        with open(file_path, "r") as f:
            data = json.load(f)
        
        # Parse the JSON data into SentimentAnalysisData model for validation
        sentiment_data = SentimentAnalysisData(**data)
        print(f"✅ Successfully extracted {len(sentiment_data.segments)} segments from {filename}")
        return sentiment_data.segments
    except Exception as e:
        filename = os.path.basename(file_path) if file_path else "unknown"
        print(f"❌ Error extracting segments from {filename}: {e}")
        return []

def analyze_sentiment_with_twelvelabs(request: SentimentAnalysisRequest) -> SentimentAnalysisResponse:
    """Helper function to analyze sentiment using Twelve Labs"""
    try:
        print(f"🎬 Starting sentiment analysis for video ID: {request.video_id}")
        response = prompt_twelvelabs(request.video_id, request.prompt or extract_info_prompt)
        
        if response and hasattr(response, 'data'):
            print(f"✅ Sentiment analysis completed successfully for video ID: {request.video_id}")
            cleaned_json = clean_llm_string_output_to_json(response.data)
            
            # Validate the JSON structure
            try:
                sentiment_data = SentimentAnalysisData(**cleaned_json)
                print(f"📊 Analysis results - Video: '{sentiment_data.video_title}' | Duration: {sentiment_data.video_length}s | Segments: {len(sentiment_data.segments)} | Overall mood: {sentiment_data.overall_mood}")
            except Exception as validation_error:
                print(f"❌ Validation error for video ID {request.video_id}: {validation_error}")
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
                print(f"💾 Analysis saved to: {os.path.basename(exported_file)} for video '{sentiment_data.video_title}'")
            
            return SentimentAnalysisResponse(
                sentiment_analysis=sentiment_data,
                file_path=exported_file,
                success=True,
                error_message=None
            )
        else:
            print(f"⚠️ No data received from Twelve Labs for video ID: {request.video_id}")
            return SentimentAnalysisResponse(
                sentiment_analysis="No analysis data received",
                file_path=None,
                success=False,
                error_message="No data received from Twelve Labs"
            )
            
    except Exception as e:
        print(f"❌ Error during sentiment analysis for video ID {request.video_id}: {str(e)}")
        return SentimentAnalysisResponse(
            sentiment_analysis=f"Analysis failed: {str(e)}",
            file_path=None,
            success=False,
            error_message=str(e)
        )

def process_video_with_sentiment(request: VideoProcessingRequest) -> None:
    """Process video with FFmpeg based on sentiment analysis"""
    # TODO: Implement FFmpeg video processing based on sentiment analysis
    # TODO: Use sentiment timestamps to create video segments
    # TODO: Apply different filters/effects based on emotional content
    # TODO: Stitch segments together with transitions
    # TODO: Generate final processed video at request.output_path
    filename = os.path.basename(request.file_path)
    output_filename = os.path.basename(request.output_path)
    print(f"🎬 Processing video: {filename} -> {output_filename} (Job: {request.job_id})")
    print(f"📊 Video segments to process: {len(request.sentiment_data.segments)}")
    
    # Placeholder implementation
    pass

def process_video_segments(request: VideoProcessingRequest) -> VideoProcessingResult:
    """Helper function to process video with FFmpeg based on sentiment"""
    try:
        # This would call your FFmpeg processing logic
        output_path = f'../processed_videos/{request.job_id}_processed.mp4'
        
        input_filename = os.path.basename(request.file_path)
        output_filename = os.path.basename(output_path)
        
        print(f"🎬 Starting video processing for job: {request.job_id}")
        print(f"📁 Input: {input_filename}")
        print(f"📁 Output: {output_filename}")
        print(f"🎯 Video title: '{request.sentiment_data.video_title}'")
        print(f"⏱️ Duration: {request.sentiment_data.video_length}s")
        
        # Create audio picking request
        audio_request = AudioPickingRequest(
            sentiment_data=request.sentiment_data,
            original_video_path=request.file_path,
            output_video_path=output_path,
            audio_library=AudioLibrary(),  # Use default audio library
            global_volume=0.3,  # Background music at 30% volume
            crossfade_duration="1.0"  # 1 second crossfade between segments
        )
        
        # Use extracted audio picker logic for Step 3
        from audio_processor_core import process_audio_for_pipeline_step3
        segments_with_audio = process_audio_for_pipeline_step3(audio_request.sentiment_data, audio_request.global_volume)
        
        print(f"✅ Step 3 Complete: Audio selection finished for '{request.sentiment_data.video_title}'!")
        print(f"📊 Generated {len(segments_with_audio)} audio segments for background music")
        
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
        print(f"🎬 FFmpeg processing summary for '{request.sentiment_data.video_title}' (Job: {request.job_id}):")
        video_segments = [s for s in ffmpeg_request.input_segments if s.file_type == "video"]
        audio_segments = [s for s in ffmpeg_request.input_segments if s.file_type == "audio"]
        
        print(f"  📹 Video tracks: {len(video_segments)}")
        print(f"  🎵 Audio tracks: {len(audio_segments)}")
        
        for i, segment in enumerate(audio_segments):
            sentiment = segment.metadata.get("sentiment", "unknown") if segment.metadata else "unknown"
            music_style = segment.metadata.get("music_style", "unknown") if segment.metadata else "unknown"
            audio_file = os.path.basename(segment.file_path)
            print(f"    Audio {i+1}: {audio_file} | {sentiment} | {music_style} | Vol: {segment.volume:.2f}")
        
        # Calculate actual duration from segments
        max_end_time = max(seg.end_time for seg in request.sentiment_data.segments)
        duration = seconds_to_time_format(max_end_time)
        
        print(f"✅ Video processing prepared for '{request.sentiment_data.video_title}' | Total duration: {duration}")
        
        return VideoProcessingResult(
            output_path=output_path,
            segments=request.sentiment_data.segments,
            duration=duration,
            success=True,
            error_message=None
        )
    except Exception as e:
        input_filename = os.path.basename(request.file_path) if request.file_path else "unknown"
        print(f"❌ Error processing video '{input_filename}' (Job: {request.job_id}): {e}")
        return VideoProcessingResult(
            output_path="",
            segments=[],
            duration="00:00:00",
            success=False,
            error_message=str(e)
        )

def process_single_video_in_batch(video_result: VideoAnalysisResult, audio_library: AudioLibrary) -> VideoAnalysisResult:
    """
    Process a single video within a multi-video batch
    Returns updated VideoAnalysisResult with sentiment analysis and audio selection
    """
    try:
        print(f"🎯 Processing video {video_result.video_index + 1}: '{video_result.filename}'")
        print(f"📁 File path: {os.path.basename(video_result.file_path)}")
        
        # Step 1: Upload to Twelve Labs
        print(f"☁️ Uploading '{video_result.filename}' to Twelve Labs...")
        video_id = upload_video_to_twelvelabs(video_result.file_path)
        if not video_id:
            raise RuntimeError(f"Failed to upload '{video_result.filename}' to Twelve Labs")
        
        video_result.twelve_labs_video_id = video_id
        print(f"✅ '{video_result.filename}' uploaded successfully | Video ID: {video_id}")
        
        # Step 2: Sentiment analysis
        print(f"🤖 Analyzing sentiment for '{video_result.filename}'...")
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed for '{video_result.filename}': {sentiment_result.error_message}")
        
        video_result.sentiment_analysis = sentiment_result
        
        # Step 3: Audio selection
        if isinstance(sentiment_result.sentiment_analysis, SentimentAnalysisData):
            sentiment_data = sentiment_result.sentiment_analysis
            video_result.video_length = sentiment_data.video_length
            
            print(f"🎵 Step 3: Selecting background music tracks for '{video_result.filename}' | Duration: {sentiment_data.video_length}s")
            
            # Use extracted audio processor logic for multi-video pipeline
            from audio_processor_core import process_tracks_and_create_audio_segments, log_pipeline_step3_results
            segments_with_audio = process_tracks_and_create_audio_segments(sentiment_data, global_volume=0.3)
            video_result.segments_with_audio = segments_with_audio
            
            print(f"✅ Audio track selection complete for '{video_result.filename}' | Selected music for {len(segments_with_audio)} segments")
            
            # Use extracted logging for this video in multi-video pipeline
            print(f"🎼 CHOSEN TRACKS for '{video_result.filename}':")
            if segments_with_audio:
                for i, segment in enumerate(segments_with_audio):
                    if segment.audio_selection:
                        audio_filename = os.path.basename(segment.audio_selection.audio_file)
                        duration = segment.end_time - segment.start_time
                        print(f"  ✓ {audio_filename} | {segment.start_time}s→{segment.end_time}s ({duration:.1f}s) | {segment.music_style}/{segment.sentiment}")
                print(f"  📊 Total: {sum(seg.end_time - seg.start_time for seg in segments_with_audio):.1f}s background music")
            else:
                print(f"  ⚠️ No tracks selected for '{video_result.filename}'")
        
        video_result.success = True
        print(f"🎉 Successfully processed video {video_result.video_index + 1}: '{video_result.filename}'")
        return video_result
        
    except Exception as e:
        print(f"❌ Error processing video {video_result.video_index + 1} '{video_result.filename}': {str(e)}")
        video_result.success = False
        video_result.error_message = str(e)
        return video_result 