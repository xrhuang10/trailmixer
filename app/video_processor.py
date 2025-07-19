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
    VideoAnalysisResult, AudioSelection, VideoSegmentWithAudio
)

# Import Twelve Labs functions
from twelvelabs_client import upload_video_to_twelvelabs, prompt_twelvelabs, clean_llm_string_output_to_json, export_to_json_file
from prompts.extract_info import extract_info_prompt
from audio_picker import map_sentiment_to_filename, get_music_file_paths
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
        
        # Step 3: Audio selection using audio_picker logic
        print(f"🎵 Step 3: Starting audio selection for '{request.sentiment_data.video_title}'...")
        segments_with_audio = []
        
        # Validate music data using audio_picker logic
        music_data = getattr(audio_request.sentiment_data, 'music', None)
        if not music_data or not hasattr(music_data, 'tracks') or not music_data.tracks:
            print("❌ No music tracks found in sentiment data")
        else:
            tracks = music_data.tracks
            print(f"🎼 Found {len(tracks)} music track(s) to process")
            
            # Process each music track using audio_picker functions
            for i, track in enumerate(tracks):
                track_dict = track.dict() if hasattr(track, 'dict') else track
                
                start_time = track_dict.get('start', 0)
                end_time = track_dict.get('end', 60)
                style = track_dict.get('style', 'Pop')
                sentiment = track_dict.get('sentiment', 'calm')
                intensity = track_dict.get('intensity', 'medium')
                
                track_duration = end_time - start_time
                print(f"🎼 Processing track {i+1}/{len(tracks)}: '{sentiment}' ({style}, {intensity})")
                print(f"   ⏱️ Timing: {start_time}s - {end_time}s (duration: {track_duration:.1f}s)")
                
                # Map sentiment to filename using audio_picker function
                filename = map_sentiment_to_filename(sentiment)
                
                # Create file path based on style and sentiment
                style_lower = style.lower()
                style_mappings = {
                    'pop': 'pop',
                    'hip hop': 'hiphop',
                    'hiphop': 'hiphop',
                    'classical': 'classical',
                    'electronic': 'pop',  # Fallback
                    'meme': 'pop'  # Fallback
                }
                style_dir = style_mappings.get(style_lower, 'pop')
                music_file_path = os.path.join('..', 'music', style_dir, f'{filename}.mp3')
                
                # Check if file exists
                if os.path.exists(music_file_path):
                    # Determine volume based on intensity
                    intensity_lower = intensity.lower()
                    if intensity_lower == 'high':
                        volume = 0.5 * audio_request.global_volume
                        fade_duration = "0.2"
                    elif intensity_lower == 'medium':
                        volume = 0.3 * audio_request.global_volume
                        fade_duration = "0.5"
                    else:  # low
                        volume = 0.2 * audio_request.global_volume
                        fade_duration = "1.0"
                    
                    # Create audio selection
                    audio_selection = AudioSelection(
                        audio_file=music_file_path,
                        volume=volume,
                        fade_in=fade_duration,
                        fade_out=fade_duration
                    )
                    
                    # Create video segment with audio
                    segment_with_audio = VideoSegmentWithAudio(
                        start_time=start_time,
                        end_time=end_time,
                        sentiment=sentiment,
                        music_style=style,
                        intensity=intensity,
                        audio_selection=audio_selection
                    )
                    
                    segments_with_audio.append(segment_with_audio)
                    
                    selected_filename = os.path.basename(music_file_path)
                    print(f"   ✅ Assigned: {selected_filename} | Volume: {volume:.3f}")
                else:
                    print(f"   ❌ Music file not found: {music_file_path}")
            
            # Log chosen tracks summary
            if segments_with_audio:
                print(f"\n🎼 STEP 3 RESULTS - CHOSEN TRACKS:")
                print(f"{'='*55}")
                for i, segment in enumerate(segments_with_audio):
                    audio_filename = os.path.basename(segment.audio_selection.audio_file)
                    duration = segment.end_time - segment.start_time
                    print(f"✓ Track {i+1}: {audio_filename}")
                    print(f"  📍 {segment.start_time}s→{segment.end_time}s ({duration:.1f}s) | {segment.music_style}/{segment.sentiment}")
                    print(f"  🔊 Vol: {segment.audio_selection.volume:.3f} | Intensity: {segment.intensity}")
                    print(f"  📁 File: {segment.audio_selection.audio_file}")
                
                total_audio_time = sum(seg.end_time - seg.start_time for seg in segments_with_audio)
                coverage_percentage = (total_audio_time / audio_request.sentiment_data.video_length) * 100 if audio_request.sentiment_data.video_length > 0 else 0
                print(f"📊 Total background music: {total_audio_time:.1f}s of {audio_request.sentiment_data.video_length}s video ({coverage_percentage:.1f}%)")
                print(f"{'='*55}")
        
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
        
        # Execute the FFmpeg request
        print(f"🎬 Starting FFmpeg processing for '{request.sentiment_data.video_title}' (Job: {request.job_id})...")
        try:
            from ffmpeg_stitch import stitch_ffmpeg_request
            result_path = stitch_ffmpeg_request(ffmpeg_request)
            print(f"✅ FFmpeg processing completed successfully! Output saved to: {os.path.basename(result_path)}")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ FFmpeg processing failed: {error_msg}")
            raise RuntimeError(f"FFmpeg processing failed: {error_msg}")
        
        # Calculate actual duration from segments
        max_end_time = max(seg.end_time for seg in request.sentiment_data.segments)
        duration = seconds_to_time_format(max_end_time)
        
        print(f"✅ Video processing completed for '{request.sentiment_data.video_title}' | Total duration: {duration}")
        
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
            
            # Audio selection using audio_picker logic for multi-video pipeline
            segments_with_audio = []
            music_data = getattr(sentiment_data, 'music', None)
            if not music_data or not hasattr(music_data, 'tracks') or not music_data.tracks:
                print("❌ No music tracks found in sentiment data")
            else:
                tracks = music_data.tracks
                for i, track in enumerate(tracks):
                    track_dict = track.dict() if hasattr(track, 'dict') else track
                    
                    start_time = track_dict.get('start', 0)
                    end_time = track_dict.get('end', 60)
                    style = track_dict.get('style', 'Pop')
                    sentiment = track_dict.get('sentiment', 'calm')
                    intensity = track_dict.get('intensity', 'medium')
                    
                    # Map sentiment to filename using audio_picker function
                    filename = map_sentiment_to_filename(sentiment)
                    
                    # Create file path
                    style_lower = style.lower()
                    style_mappings = {'pop': 'pop', 'hip hop': 'hiphop', 'hiphop': 'hiphop', 'classical': 'classical', 'electronic': 'pop', 'meme': 'pop'}
                    style_dir = style_mappings.get(style_lower, 'pop')
                    music_file_path = os.path.join('..', 'music', style_dir, f'{filename}.mp3')
                    
                    if os.path.exists(music_file_path):
                        # Determine volume based on intensity
                        intensity_lower = intensity.lower()
                        if intensity_lower == 'high':
                            volume = 0.5 * 0.3  # global_volume=0.3
                            fade_duration = "0.2"
                        elif intensity_lower == 'medium':
                            volume = 0.3 * 0.3
                            fade_duration = "0.5"
                        else:  # low
                            volume = 0.2 * 0.3
                            fade_duration = "1.0"
                        
                        audio_selection = AudioSelection(
                            audio_file=music_file_path,
                            volume=volume,
                            fade_in=fade_duration,
                            fade_out=fade_duration
                        )
                        
                        segment_with_audio = VideoSegmentWithAudio(
                            start_time=start_time,
                            end_time=end_time,
                            sentiment=sentiment,
                            music_style=style,
                            intensity=intensity,
                            audio_selection=audio_selection
                        )
                        
                        segments_with_audio.append(segment_with_audio)
            
            video_result.segments_with_audio = segments_with_audio
            print(f"✅ Audio track selection complete for '{video_result.filename}' | Selected music for {len(segments_with_audio)} segments")
            
            # Log chosen tracks for this video in multi-video pipeline
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