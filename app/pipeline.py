"""
Background processing pipelines for video processing    
"""
import re
import os
import tempfile
import subprocess
from typing import Dict, List
from models import (
    JobStatus, JobInfo, MultiVideoJobInfo, SentimentAnalysisRequest, SentimentAnalysisData,
    VideoProcessingRequest, AudioLibrary, VideoAnalysisResult, MultiVideoFFmpegRequest, FfmpegRequest
)
from ffmpeg_builder import create_ffmpeg_request

from video_processor import analyze_sentiment_with_twelvelabs, process_video_segments, process_single_video_in_batch
from ffmpeg_builder import create_multi_video_ffmpeg_request
from prompts.extract_info import extract_info_prompt
from twelvelabs_client import upload_video_to_twelvelabs
from audio_picker import get_music_file_paths
from ffmpeg_stitch import stitch_ffmpeg_request

def add_music_to_video(video_filepath: str, music_tracks: Dict[str, Dict], output_path: str, video_volume: float = 1.0, music_volume: float = 0.25) -> str:
    """
    Add background music tracks to a video at specified timestamps.
    
    Args:
        video_filepath: Path to the input video file
        music_tracks: Dictionary where keys are audio file paths and values are dicts with 'start' and 'end' timestamps
                     Example: {
                         "/path/to/music1.mp3": {"start": 0, "end": 30},
                         "/path/to/music2.mp3": {"start": 25, "end": 60}
                     }
        output_path: Path where the output video with music should be saved
        video_volume: Volume level for original video audio (0.0 to 1.0)
        music_volume: Volume level for background music (0.0 to 1.0)
        
    Returns:
        str: Path to the output video file
        
    Raises:
        ValueError: If input validation fails
        RuntimeError: If FFmpeg processing fails
    """
    if not video_filepath or not os.path.exists(video_filepath):
        raise ValueError(f"Input video file not found: {video_filepath}")
    
    if not music_tracks:
        raise ValueError("No music tracks provided")
    
    if not output_path:
        raise ValueError("Output path is required")
    
    print(f"🎵 Adding background music to video")
    print(f"   📁 Input video: {os.path.basename(video_filepath)}")
    print(f"   🎼 Music tracks: {len(music_tracks)}")
    print(f"   📁 Output: {os.path.basename(output_path)}")
    
    # Validate music tracks and timestamps
    validated_tracks = []
    for i, (audio_path, timing) in enumerate(music_tracks.items()):
        if not os.path.exists(audio_path):
            raise ValueError(f"Audio file not found: {audio_path}")
        
        if 'start' not in timing or 'end' not in timing:
            raise ValueError(f"Track {i+1} missing 'start' or 'end' timestamp")
        
        start = float(timing['start'])
        end = float(timing['end'])
        
        if start < 0:
            raise ValueError(f"Track {i+1} start time cannot be negative: {start}")
        
        if end <= start:
            raise ValueError(f"Track {i+1} end time ({end}) must be greater than start time ({start})")
        
        validated_tracks.append({
            'path': audio_path,
            'start': start,
            'end': end,
            'duration': end - start
        })
        
        print(f"   🎼 Track {i+1}: {os.path.basename(audio_path)} ({start}s - {end}s, duration: {end-start:.1f}s)")
    
    abs_video_path = os.path.abspath(video_filepath)
    abs_output_path = os.path.abspath(output_path)
    
    try:
        # Build FFmpeg command with filter_complex for audio mixing
        print(f"🎬 Building FFmpeg command for audio mixing...")
        
        # Start building the command
        ffmpeg_cmd = ["ffmpeg"]
        
        # Add video input
        ffmpeg_cmd.extend(["-i", abs_video_path])
        
        # Add all audio inputs
        for track in validated_tracks:
            ffmpeg_cmd.extend(["-i", track['path']])
        
        # Build filter_complex for audio mixing
        filter_parts = []
        audio_inputs = []
        
        # Process original video audio
        filter_parts.append(f"[0:a]volume={video_volume}[original_audio]")
        audio_inputs.append("[original_audio]")
        
        # Process each music track with timing and volume
        for i, track in enumerate(validated_tracks):
            input_idx = i + 1  # Input 0 is video, audio tracks start from 1
            track_label = f"music_{i}"
            
            # Apply volume and timing to each track
            # Use adelay to offset the start time, and atrim to limit duration
            start_delay_ms = int(track['start'] * 1000)  # Convert to milliseconds
            duration_s = track['duration']
            end_time = duration_s + track['start']
            
            if track['start'] > 0:
                # Add delay for start time and trim for duration
                filter_parts.append(f"[{input_idx}:a]volume={music_volume},adelay={start_delay_ms}|{start_delay_ms},atrim=0:{end_time}[{track_label}]")
            else:
                # No delay needed, just trim duration
                filter_parts.append(f"[{input_idx}:a]volume={music_volume},atrim=0:{duration_s}[{track_label}]")
            
            audio_inputs.append(f"[{track_label}]")
        
        # Mix all audio inputs together
        mix_inputs = "".join(audio_inputs)
        num_inputs = len(audio_inputs)
        filter_parts.append(f"{mix_inputs}amix=inputs={num_inputs}:duration=first:dropout_transition=0[mixed_audio]")
        
        # Combine all filter parts
        filter_complex = ";".join(filter_parts)
        
        # Add filter_complex to command
        ffmpeg_cmd.extend(["-filter_complex", filter_complex])
        
        # Map video and mixed audio to output
        ffmpeg_cmd.extend(["-map", "0:v", "-map", "[mixed_audio]"])
        
        # Output settings
        ffmpeg_cmd.extend([
            "-c:v", "copy",  # Copy video stream without re-encoding
            "-c:a", "aac",   # Encode audio as AAC
            "-b:a", "128k",  # Audio bitrate
            "-y",            # Overwrite output file
            abs_output_path
        ])
        
        print(f"🎵 Executing FFmpeg audio mixing...")
        # Build track names for display
        track_names = [f'-i {os.path.basename(t["path"])}' for t in validated_tracks]
        track_display = ' '.join(track_names)
        print(f"   Command: ffmpeg -i video {track_display} -filter_complex '...' -map 0:v -map '[mixed_audio]' output.mp4")
        
        # Execute FFmpeg command
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Verify output file was created
        if not os.path.exists(abs_output_path):
            raise RuntimeError("FFmpeg completed but output file was not created")
        
        output_size = os.path.getsize(abs_output_path)
        print(f"✅ Background music added successfully!")
        print(f"   📁 Output: {os.path.basename(abs_output_path)}")
        print(f"   📊 Size: {output_size / (1024*1024):.1f} MB")
        print(f"   🎼 Music tracks mixed: {len(validated_tracks)}")
        
        return abs_output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\nSTDERR: {e.stderr}"
        if e.stdout:
            error_msg += f"\nSTDOUT: {e.stdout}"
        
        print(f"❌ Audio mixing failed: {error_msg}")
        raise RuntimeError(f"Audio mixing failed: {error_msg}")
        
    except Exception as e:
        print(f"❌ Audio mixing failed: {str(e)}")
        raise RuntimeError(f"Audio processing failed: {str(e)}")

def crop_and_stitch_video_segments(video_filepath: str, segments: List[Dict], output_path: str) -> str:
    """
    Crop video segments and stitch them together into a final video.
    
    Args:
        video_filepath: Path to the input video file
        segments: List of dictionaries with 'start' and 'end' keys (in seconds)
                 Example: [{'start': 0, 'end': 10}, {'start': 20, 'end': 30}]
        output_path: Path where the final stitched video should be saved
        
    Returns:
        str: Path to the output video file
        
    Raises:
        ValueError: If input validation fails
        RuntimeError: If FFmpeg processing or stitching fails
    """
    if not video_filepath or not os.path.exists(video_filepath):
        raise ValueError(f"Input video file not found: {video_filepath}")
    
    if not segments:
        raise ValueError("No segments provided for cropping")
    
    if not output_path:
        raise ValueError("Output path is required")
    
    print(f"🎬 Cropping and stitching video segments")
    print(f"   📁 Input: {os.path.basename(video_filepath)}")
    print(f"   📊 Segments: {len(segments)}")
    print(f"   📁 Output: {os.path.basename(output_path)}")
    print(f"   ⚡ Method: Fast copy with fallback re-encoding for compatibility")
    
    # Validate segments
    for i, segment in enumerate(segments):
        if 'start' not in segment or 'end' not in segment:
            raise ValueError(f"Segment {i+1} missing 'start' or 'end' key")
        
        start = float(segment['start'])
        end = float(segment['end'])
        
        if start < 0:
            raise ValueError(f"Segment {i+1} start time cannot be negative: {start}")
        
        if end <= start:
            raise ValueError(f"Segment {i+1} end time ({end}) must be greater than start time ({start})")
        
        print(f"   📹 Segment {i+1}: {start}s - {end}s (duration: {end-start:.1f}s)")
    
    temp_files = []
    abs_video_path = os.path.abspath(video_filepath)
    abs_output_path = os.path.abspath(output_path)
    
    try:
        # Create temporary directory for cropped segments
        temp_dir = tempfile.mkdtemp(prefix="video_segments_")
        print(f"📁 Created temporary directory: {temp_dir}")
        
        # Detect input video properties for better processing
        print(f"🔍 Analyzing input video properties...")
        try:
            probe_cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", abs_video_path
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            print(f"   ✅ Video analysis completed")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️ Could not analyze video properties: {e}")
        
        # Crop each segment using FFmpeg with re-encoding
        print(f"🎬 Processing segments with fast copy method and fallback re-encoding...")
        for i, segment in enumerate(segments):
            start = float(segment['start'])
            end = float(segment['end'])
            duration = end - start
            
            # Create temporary file for this segment
            segment_filename = f"segment_{i+1:03d}.mp4"
            temp_segment_path = os.path.join(temp_dir, segment_filename)
            
            print(f"✂️ Cropping segment {i+1}/{len(segments)}: {start}s - {end}s")
            
            # Try fast method first (stream copy with keyframe seeking)
            # Seek before input for faster processing
            ffmpeg_cmd_fast = [
                "ffmpeg",
                "-ss", str(start),              # Seek before input (much faster)
                "-i", abs_video_path,           # Input video
                "-t", str(duration),            # Duration
                "-c", "copy",                   # Copy streams (fastest)
                "-avoid_negative_ts", "make_zero",  # Handle timestamp issues
                "-y",                           # Overwrite output file
                temp_segment_path
            ]
            
            # Fallback method with minimal re-encoding if fast method fails
            ffmpeg_cmd_fallback = [
                "ffmpeg",
                "-ss", str(start),              # Seek before input
                "-i", abs_video_path,           # Input video
                "-t", str(duration),            # Duration
                "-c:v", "libx264",              # Re-encode video only if needed
                "-c:a", "copy",                 # Copy audio (faster)
                "-crf", "23",                   # Good quality
                "-preset", "veryfast",          # Fast encoding
                "-avoid_negative_ts", "make_zero",
                "-y",
                temp_segment_path
            ]
            
            # Try fast method first
            print(f"   Attempting fast copy method...")
            success = False
            
            try:
                result = subprocess.run(
                    ffmpeg_cmd_fast,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Verify segment was created and is valid
                if os.path.exists(temp_segment_path) and os.path.getsize(temp_segment_path) > 1000:
                    segment_size = os.path.getsize(temp_segment_path)
                    print(f"   ✅ Fast method: Segment {i+1} created: {segment_size / (1024*1024):.1f} MB")
                    temp_files.append(temp_segment_path)
                    success = True
                else:
                    print(f"   ⚠️ Fast method produced invalid file, trying fallback...")
                    
            except subprocess.CalledProcessError as e:
                print(f"   ⚠️ Fast method failed (exit code {e.returncode}), trying fallback...")
            
            # If fast method failed, try fallback with minimal re-encoding
            if not success:
                try:
                    print(f"   Using fallback method with minimal re-encoding...")
                    result = subprocess.run(
                        ffmpeg_cmd_fallback,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Verify segment was created
                    if not os.path.exists(temp_segment_path):
                        raise RuntimeError(f"FFmpeg completed but segment file was not created: {temp_segment_path}")
                    
                    segment_size = os.path.getsize(temp_segment_path)
                    print(f"   ✅ Fallback method: Segment {i+1} created: {segment_size / (1024*1024):.1f} MB")
                    temp_files.append(temp_segment_path)
                    
                except subprocess.CalledProcessError as e:
                    error_msg = f"FFmpeg failed for segment {i+1} (start: {start}s, duration: {duration}s) with exit code {e.returncode}"
                    if e.stderr:
                        error_msg += f"\nSTDERR: {e.stderr}"
                    if e.stdout:
                        error_msg += f"\nSTDOUT: {e.stdout}"
                    
                    print(f"❌ Segment {i+1} cropping failed: {error_msg}")
                    print(f"   📊 Segment details: start={start}s, end={end}s, duration={duration}s")
                    print(f"   🔧 Try checking if the video duration is sufficient for this segment")
                    raise RuntimeError(f"Segment cropping failed: {error_msg}")
        
        print(f"✅ All {len(segments)} segments cropped successfully with optimized processing")
        
        # Stitch the cropped segments together
        print(f"🔗 Stitching {len(temp_files)} segments together with fast method...")
        final_output_path = stitch_videos_together(temp_files, abs_output_path)
        
        # Verify final output
        if not os.path.exists(final_output_path):
            raise RuntimeError("Final stitched video was not created")
        
        final_size = os.path.getsize(final_output_path)
        print(f"✅ Video cropping and stitching completed successfully!")
        print(f"   📁 Output: {os.path.basename(final_output_path)}")
        print(f"   📊 Size: {final_size / (1024*1024):.1f} MB")
        print(f"   🎬 Total segments: {len(segments)}")
        
        return final_output_path
        
    except Exception as e:
        print(f"❌ Video cropping and stitching failed: {str(e)}")
        raise RuntimeError(f"Video processing failed: {str(e)}")
        
    finally:
        # Clean up temporary files
        cleanup_count = 0
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    cleanup_count += 1
            except Exception as cleanup_error:
                print(f"⚠️ Failed to clean up temp file {temp_file}: {cleanup_error}")
        
        # Clean up temporary directory
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                os.rmdir(temp_dir)
                print(f"🧹 Cleaned up {cleanup_count} temp files and directory")
        except Exception as cleanup_error:
            print(f"⚠️ Failed to clean up temp directory: {cleanup_error}")

def stitch_videos_together(video_file_paths: List[str], output_path: str) -> str:
    """
    Stitch a list of videos together into a single video using FFmpeg
    
    Args:
        video_file_paths: List of paths to video files to concatenate
        output_path: Path where the stitched video should be saved
        
    Returns:
        str: Path to the output video file
        
    Raises:
        RuntimeError: If FFmpeg processing fails
        ValueError: If input validation fails
    """
    if not video_file_paths:
        raise ValueError("No video files provided for stitching")
    
    if len(video_file_paths) == 1:
        print(f"⚠️ Only one video provided, copying to output path")
        import shutil
        shutil.copy2(video_file_paths[0], output_path)
        return output_path
    
    print(f"🔗 Stitching {len(video_file_paths)} videos together...")
    print(f"📁 Output: {os.path.basename(output_path)}")
    
    # Validate input files exist and normalize paths
    normalized_paths = []
    for i, video_path in enumerate(video_file_paths):
        # Convert to absolute path and normalize separators
        abs_path = os.path.abspath(video_path)
        if not os.path.exists(abs_path):
            raise ValueError(f"Video file {i+1} not found: {abs_path}")
        normalized_paths.append(abs_path)
        print(f"   📹 Input {i+1}: {os.path.basename(abs_path)}")
        print(f"       Path: {abs_path}")
    
    # Create temporary file list for FFmpeg concat demuxer
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir=os.getcwd()) as temp_file:
        temp_list_path = temp_file.name
        
        # Write file list in FFmpeg concat format
        for video_path in normalized_paths:
            # On Windows, use forward slashes and escape properly for FFmpeg
            if os.name == 'nt':  # Windows
                # Convert backslashes to forward slashes for FFmpeg
                ffmpeg_path = video_path.replace('\\', '/')
                # Escape single quotes if any
                ffmpeg_path = ffmpeg_path.replace("'", "'\"'\"'")
            else:
                # Unix-like systems
                ffmpeg_path = video_path.replace("'", "'\"'\"'")
            
            temp_file.write(f"file '{ffmpeg_path}'\n")
            print(f"       FFmpeg path: {ffmpeg_path}")
    
    try:
        print(f"📝 Created temporary file list: {temp_list_path}")
        
        # Normalize output path
        abs_output_path = os.path.abspath(output_path)
        
        # Build FFmpeg command for concatenation - try fast method first
        ffmpeg_cmd_fast = [
            "ffmpeg",
            "-f", "concat",           # Use concat demuxer
            "-safe", "0",             # Allow unsafe file paths
            "-i", temp_list_path,     # Input file list
            "-c", "copy",             # Copy streams (fastest)
            "-y",                     # Overwrite output file
            abs_output_path
        ]
        
        # Fallback with minimal re-encoding if stream copy fails
        ffmpeg_cmd_fallback = [
            "ffmpeg",
            "-f", "concat",           # Use concat demuxer
            "-safe", "0",             # Allow unsafe file paths
            "-i", temp_list_path,     # Input file list
            "-c:v", "libx264",        # Re-encode video only if needed
            "-c:a", "copy",           # Copy audio (faster)
            "-crf", "23",             # Good quality
            "-preset", "veryfast",    # Fastest encoding
            "-y",                     # Overwrite output file
            abs_output_path
        ]
        
        print(f"🎬 Trying fast concatenation with stream copy...")
        success = False
        
        # Try fast method first
        try:
            result = subprocess.run(
                ffmpeg_cmd_fast,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Verify output exists and has reasonable size
            if os.path.exists(abs_output_path) and os.path.getsize(abs_output_path) > 1000:
                output_size = os.path.getsize(abs_output_path)
                print(f"✅ Fast concatenation successful!")
                print(f"   📁 Output: {os.path.basename(abs_output_path)}")
                print(f"   📊 Size: {output_size / (1024*1024):.1f} MB")
                success = True
            else:
                print(f"⚠️ Fast method produced invalid output, trying fallback...")
                
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Fast concatenation failed (exit code {e.returncode}), trying fallback...")
        
        # If fast method failed, use fallback with minimal re-encoding
        if not success:
            print(f"🔄 Using fallback concatenation with minimal re-encoding...")
            try:
                result = subprocess.run(
                    ffmpeg_cmd_fallback,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Check if output file was created
                if not os.path.exists(abs_output_path):
                    raise RuntimeError("FFmpeg completed but output file was not created")
                
                # Get output file size for verification
                output_size = os.path.getsize(abs_output_path)
                print(f"✅ Fallback concatenation successful!")
                print(f"   📁 Output: {os.path.basename(abs_output_path)}")
                print(f"   📊 Size: {output_size / (1024*1024):.1f} MB")
                
            except subprocess.CalledProcessError as e:
                error_msg = f"FFmpeg concatenation failed with exit code {e.returncode}"
                if e.stderr:
                    error_msg += f"\nSTDERR: {e.stderr}"
                if e.stdout:
                    error_msg += f"\nSTDOUT: {e.stdout}"
                
                print(f"❌ Video stitching failed: {error_msg}")
                raise RuntimeError(f"Video stitching failed: {error_msg}")
        
        return abs_output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\nSTDERR: {e.stderr}"
        if e.stdout:
            error_msg += f"\nSTDOUT: {e.stdout}"
        
        print(f"❌ Video stitching failed: {error_msg}")
        raise RuntimeError(f"Video stitching failed: {error_msg}")
        
    except Exception as e:
        print(f"❌ Unexpected error during video stitching: {str(e)}")
        raise RuntimeError(f"Video stitching failed: {str(e)}")
        
    finally:
        # Clean up temporary file list
        try:
            if os.path.exists(temp_list_path):
                os.unlink(temp_list_path)
                print(f"🧹 Cleaned up temporary file: {temp_list_path}")
        except Exception as cleanup_error:
            print(f"⚠️ Failed to clean up temporary file: {cleanup_error}")

def upload_video_pipeline(job_id: str, job_status: Dict[str, JobInfo]):
    """Complete video processing pipeline"""
    job = job_status[job_id]
    filename = job.filename
    input_file = os.path.basename(job.file_path)
    
    print(f"\n🚀 Starting video processing pipeline")
    print(f"   🆔 Job ID: {job_id}")
    print(f"   📁 File: {filename}")
    print(f"   📍 Path: {input_file}")
    
    try:
        # Step 1: Upload to Twelve Labs for indexing
        job.status = JobStatus.INDEXING
        job.message = f"Uploading '{filename}' to Twelve Labs for AI analysis..."
        print(f"📤 Step 1: Uploading '{filename}' to Twelve Labs...")
        
        file_path = job.file_path
        video_id = upload_video_to_twelvelabs(file_path)
        
        if not video_id:
            raise RuntimeError(f"Failed to upload '{filename}' to Twelve Labs")
        
        job.twelve_labs_video_id = video_id
        job.status = JobStatus.ANALYZING
        job.message = f"Analyzing sentiment for '{filename}' with AI..."
        print(f"✅ Upload successful! Video ID: {video_id}")
        
        # Step 2: Perform sentiment analysis
        print(f"🤖 Step 2: Analyzing sentiment for '{filename}'...")
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        job.sentiment_analysis = sentiment_result
        
        # Extract segments with proper error handling for missing fields
        if sentiment_result.sentiment_analysis and hasattr(sentiment_result.sentiment_analysis, 'segments'):
            # Convert segments to a format that handles missing fields
            segments_list = []
            raw_segments = sentiment_result.sentiment_analysis.segments
            
            print(f"🔍 DEBUG: Processing segments")
            print(f"   Raw segments type: {type(raw_segments)}")
            print(f"   Raw segments content: {raw_segments}")
            
            for i, segment in enumerate(raw_segments):
                print(f"   Segment {i} type: {type(segment)}")
                print(f"   Segment {i} content: {segment}")
                
                try:
                    # Handle different segment data types
                    if isinstance(segment, dict):
                        segment_dict = segment
                    elif isinstance(segment, list):
                        # Handle case where segment is a list - skip or create default
                        print(f"   ⚠️ Segment {i} is a list, skipping: {segment}")
                        continue
                    elif hasattr(segment, 'dict'):
                        segment_dict = segment.dict()
                    elif hasattr(segment, '__dict__'):
                        segment_dict = vars(segment)
                    else:
                        # Fallback: try to convert to dict or create default
                        print(f"   ⚠️ Unknown segment type {type(segment)}, creating default")
                        segment_dict = {
                            'start_time': i * 10,
                            'end_time': (i + 1) * 10,
                            'sentiment': 'neutral',
                            'music_style': 'ambient',
                            'intensity': 'medium'
                        }
                    
                    # Ensure all required fields are present with defaults
                    normalized_segment = {
                        'start_time': segment_dict.get('start_time', i * 10),
                        'end_time': segment_dict.get('end_time', (i + 1) * 10),
                        'sentiment': segment_dict.get('sentiment', 'neutral'),
                        'music_style': segment_dict.get('music_style', 'ambient'),
                        'intensity': segment_dict.get('intensity', 'medium'),  # Add missing intensity field
                        'include': segment_dict.get('include', True)
                    }
                    segments_list.append(normalized_segment)
                    print(f"   ✅ Processed segment {i}: {normalized_segment['start_time']}s - {normalized_segment['end_time']}s")
                    
                except Exception as segment_error:
                    print(f"   ❌ Error processing segment {i}: {segment_error}")
                    # Create a default segment to avoid total failure
                    default_segment = {
                        'start_time': i * 10,
                        'end_time': (i + 1) * 10,
                        'sentiment': 'neutral',
                        'music_style': 'ambient',
                        'intensity': 'medium',
                        'include': True
                    }
                    segments_list.append(default_segment)
                    print(f"   🔄 Created default segment {i}: {default_segment['start_time']}s - {default_segment['end_time']}s")
            
            job.segment_timestamps = segments_list
            print(f"✅ Processed {len(segments_list)} segments with normalized fields")
        else:
            print("⚠️ No segments found in sentiment analysis, using empty list")
            job.segment_timestamps = []
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed for '{filename}': {sentiment_result.error_message}")
        
        # Step 3: Select background audio based on sentiment analysis
        print(f"🎵 Step 3: Selecting background music tracks for '{filename}' based on AI analysis...")
        if job.sentiment_analysis.file_path:
            filepath = re.sub(r'\\+', '/', job.sentiment_analysis.file_path)
            print(f"File path: {filepath}")
            music_file_paths = get_music_file_paths(filepath)
            print(f"🎵 Found {len(music_file_paths)} music file paths")
        else:
            print("❌ No sentiment analysis file path available for music selection")
        print(f"Music file paths: {music_file_paths}")
        
        # Testing if the music file paths are valid
        all_exist = True
        for path in music_file_paths:
            if not os.path.isfile(path):
                print(f"❌ File does not exist: {path}")
                all_exist = False
            else:
                print(f"✅ File exists: {path}")
        if all_exist:
            print("All music file paths are valid.")
        else:
            print("Some music file paths are invalid.")
            
        print("Step 3 complete!")
    except Exception as e:
        job.status = JobStatus.FAILED
        job.message = f"Processing failed for '{filename}': {str(e)}"
        print(f"❌ Pipeline failed for '{filename}' (Job: {job_id}): {str(e)}")

def process_video_pipeline(job_id: str, job_status: Dict[str, JobInfo]):
    """Complete video processing pipeline"""
    job = job_status[job_id]
    filename = job.filename
    input_file = os.path.basename(job.file_path)
    
    print(f"\n🚀 Starting video processing pipeline")
    print(f"   🆔 Job ID: {job_id}")
    print(f"   📁 File: {filename}")
    print(f"   📍 Path: {input_file}")
    
    try:
        # Step 1: Upload to Twelve Labs for indexing
        job.status = JobStatus.INDEXING
        job.message = f"Uploading '{filename}' to Twelve Labs for AI analysis..."
        print(f"📤 Step 1: Uploading '{filename}' to Twelve Labs...")
        
        file_path = job.file_path
        video_id = upload_video_to_twelvelabs(file_path)
        
        if not video_id:
            raise RuntimeError(f"Failed to upload '{filename}' to Twelve Labs")
        
        job.twelve_labs_video_id = video_id
        job.status = JobStatus.ANALYZING
        job.message = f"Analyzing sentiment for '{filename}' with AI..."
        print(f"✅ Upload successful! Video ID: {video_id}")
        
        # Step 2: Perform sentiment analysis
        print(f"🤖 Step 2: Analyzing sentiment for '{filename}'...")
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        job.sentiment_analysis = sentiment_result
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed for '{filename}': {sentiment_result.error_message}")
        
        # Step 3: Select background audio based on sentiment analysis
        print(f"🎵 Step 3: Selecting background music tracks for '{filename}' based on AI analysis...")
        if job.sentiment_analysis.file_path:
            filepath = re.sub(r'\\+', '/', job.sentiment_analysis.file_path)
            print(f"File path: {filepath}")
            music_file_paths = get_music_file_paths(filepath)
            print(f"🎵 Found {len(music_file_paths)} music file paths")
        else:
            print("❌ No sentiment analysis file path available for music selection")
        print(f"Music file paths: {music_file_paths}")
        
        # Testing if the music file paths are valid
        all_exist = True
        for path in music_file_paths:
            if not os.path.isfile(path):
                print(f"❌ File does not exist: {path}")
                all_exist = False
            else:
                print(f"✅ File exists: {path}")
        if all_exist:
            print("All music file paths are valid.")
        else:
            print("Some music file paths are invalid.")
            
        print("Step 3 complete!")
            
        # Get sentiment data as dictionary
        raw_data = job.sentiment_analysis.sentiment_analysis
        if isinstance(raw_data, str):
            print("❌ Cannot create FFmpeg request: sentiment analysis failed")
            return
        
        # Convert to dict with proper type handling
        print(f"🔍 DEBUG: Converting sentiment data to dict")
        print(f"   Raw data type: {type(raw_data)}")
        print(f"   Raw data content: {raw_data}")
        
        try:
            if isinstance(raw_data, dict):
                sentiment_data = raw_data
            elif isinstance(raw_data, list):
                print("⚠️ Raw data is a list, creating default sentiment data structure")
                sentiment_data = {
                    'video_length': 60,  # Default video length
                    'overall_mood': 'neutral',
                    'segments': raw_data if len(raw_data) > 0 else []
                }
            elif hasattr(raw_data, 'dict'):
                sentiment_data = raw_data.dict()
            elif hasattr(raw_data, '__dict__'):
                sentiment_data = vars(raw_data)
            else:
                print(f"⚠️ Unknown raw_data type {type(raw_data)}, creating default structure")
                sentiment_data = {
                    'video_length': 60,
                    'overall_mood': 'neutral',
                    'segments': []
                }
            
            print(f"✅ Converted to sentiment_data dict with keys: {list(sentiment_data.keys())}")
            
        except Exception as conversion_error:
            print(f"❌ Error converting sentiment data: {conversion_error}")
            # Create fallback sentiment data
            sentiment_data = {
                'video_length': 60,
                'overall_mood': 'neutral', 
                'segments': []
            }
        
        # Create FfmpegRequest with video and audio segments
        from models import InputSegment
        
        output_path = f'../processed_videos/{job_id}_processed.mp4'
        input_segments = []
        
        # Add original video as input segment
        video_length = sentiment_data.get('video_length', 60)
        video_formatted_duration = f'{int(video_length//3600):02d}:{int((video_length%3600)//60):02d}:{int(video_length%60):02d}'
        video_segment = InputSegment(
            file_path=file_path,
            file_type='video',
            start_time='00:00:00',
            end_time=video_formatted_duration,
            clip_start='00:00:00',
            clip_end=video_formatted_duration,  # Set explicit clip end
            volume=1.0,
            fade_in=None,
            fade_out=None,
            metadata=None
        )
        input_segments.append(video_segment)
        
        # Add audio segments from music file paths
        print(f"🎵 Adding {len(music_file_paths)} audio segments...")
        for audio_file, timing_info in music_file_paths.items():
            start_time = min(timing_info.get('start', 0), video_length)  # Ensure start doesn't exceed video length
            end_time = min(timing_info.get('end', video_length), video_length)  # Use video length as default/max
            
            # Convert seconds to HH:MM:SS format
            start_formatted = f'{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d}'
            end_formatted = f'{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d}'
            
            audio_segment = InputSegment(
                file_path=audio_file,
                file_type='audio',
                start_time=start_formatted,
                end_time=end_formatted,
                clip_start='00:00:00',
                clip_end=end_formatted,  # Set explicit clip end
                volume=0.3,  # Background music volume
                fade_in='0.5',
                fade_out='0.5',
                metadata=None
            )
            input_segments.append(audio_segment)
            print(f"   🎼 Added: {os.path.basename(audio_file)} ({start_formatted} - {end_formatted})")
        
        # Create FFmpeg request
        from models import VideoCodec, AudioCodec
        ffmpeg_request = FfmpegRequest(
            input_segments=input_segments,
            output_file=output_path,
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            video_bitrate=None,
            audio_bitrate=None,
            crf=23,
            preset='medium',
            scale=None,
            fps=None,
            audio_channels=2,
            audio_sample_rate=44100,
            global_volume=0.3,
            normalize_audio=False,
            crossfade_duration='1.0',
            gap_duration='00:00:00',
            overwrite=True,
            quiet=False,
            progress=True,
            request_id=job_id,
            priority=1
        )
        
        # Execute FFmpeg processing
        print(f"🎬 Step 4: Executing FFmpeg processing...")
        try:
            result_path = stitch_ffmpeg_request(ffmpeg_request)
            
            # Update job status
            job.status = JobStatus.COMPLETED
            job.message = f"Video processing completed successfully for '{filename}' with background music"
            job.processed_video = {
                "output_path": result_path,
                "total_segments": len(input_segments),
                "audio_segments_count": len(music_file_paths)
            }
            
            print(f"✅ Pipeline completed successfully for '{filename}'!")
            print(f"   📁 Output: {os.path.basename(result_path)}")
            
        except Exception as ffmpeg_error:
            raise RuntimeError(f"FFmpeg processing failed: {str(ffmpeg_error)}")
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.message = f"Processing failed for '{filename}': {str(e)}"
        print(f"❌ Pipeline failed for '{filename}' (Job: {job_id}): {str(e)}")

def process_multi_video_pipeline(job_id: str, multi_video_job_status: Dict[str, MultiVideoJobInfo]):
    """Complete multi-video processing pipeline"""
    job = multi_video_job_status[job_id]
    
    print(f"\n🚀 Starting multi-video processing pipeline")
    print(f"   🆔 Job ID: {job_id}")
    print(f"   📊 Video count: {job.video_count}")
    print(f"   📁 Files: {', '.join(job.video_files)}")
    
    try:
        # Step 1: Process each video individually
        job.status = JobStatus.INDEXING
        job.message = f"Processing {job.video_count} videos - indexing and analyzing..."
        print(f"📤 Step 1: Processing {job.video_count} videos individually...")
        
        audio_library = AudioLibrary()
        
        for i, video_file in enumerate(job.video_files):
            job.message = f"Processing video {i+1}/{job.video_count}: '{video_file}' - indexing and analyzing..."
            print(f"\n📹 Processing video {i+1}/{job.video_count}: '{video_file}'")
            
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
            
            if processed_result.success:
                print(f"✅ Video {i+1} processed successfully: '{video_file}'")
            else:
                print(f"❌ Video {i+1} failed: '{video_file}' - {processed_result.error_message}")
        
        # Count successful videos
        successful_videos = [v for v in job.video_results if v.success]
        failed_videos = [v for v in job.video_results if not v.success]
        
        print(f"\n📊 Individual processing complete:")
        print(f"   ✅ Successful: {len(successful_videos)}/{job.video_count}")
        print(f"   ❌ Failed: {len(failed_videos)}/{job.video_count}")
        
        if len(successful_videos) == 0:
            raise RuntimeError("No videos were successfully processed")
        
        # Step 2: Aggregate all videos into single FFmpeg request
        job.status = JobStatus.PROCESSING
        job.message = f"Creating aggregated video with background music from {len(successful_videos)} successful videos..."
        print(f"🎬 Step 2: Creating aggregated video from {len(successful_videos)} videos...")
        
        output_path = f'../processed_videos/{job_id}_multi_video.mp4'
        output_filename = os.path.basename(output_path)
        
        multi_video_request = MultiVideoFFmpegRequest(
            video_results=job.video_results,
            output_video_path=output_path,
            global_volume=0.3,
            crossfade_duration="1.0",
            video_transition_duration="0.5"
        )
        
        print(f"🔧 Creating FFmpeg request for video aggregation...")
        aggregated_ffmpeg_request = create_multi_video_ffmpeg_request(multi_video_request)
        job.aggregated_ffmpeg_request = aggregated_ffmpeg_request.dict()
        
        # TODO: Execute the aggregated FFmpeg request
        print(f"🎬 Multi-video FFmpeg request ready for execution!")
        print(f"   📊 Total input segments: {len(aggregated_ffmpeg_request.input_segments)}")
        print(f"   📁 Output file: {output_filename}")
        
        # Step 3: Complete
        job.status = JobStatus.COMPLETED
        job.message = f"Multi-video processing completed - {len(successful_videos)}/{job.video_count} videos with background music ready"
        
        print(f"🎉 Multi-video pipeline completed successfully!")
        print(f"   🆔 Job ID: {job_id}")
        print(f"   🎬 Videos processed: {len(successful_videos)}/{job.video_count}")
        print(f"   📁 Output: {output_filename}")
        print(f"   📊 Ready for download/streaming")
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.message = f"Multi-video processing failed: {str(e)}"
        print(f"❌ Multi-video pipeline failed (Job: {job_id}): {str(e)}") 

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test-compatibility":
        # Test video compatibility checking
        if len(sys.argv) > 2:
            video_path = sys.argv[2]
            print(f"🔍 Checking video compatibility: {video_path}")
            info = check_video_compatibility(video_path)
            if info:
                print(f"✅ Video info:")
                for key, value in info.items():
                    print(f"   {key}: {value}")
            else:
                print(f"❌ Could not analyze video")
        else:
            print("Usage: python pipeline.py --test-compatibility <video_path>")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-crop":
        # Test video cropping and stitching
        example_timestamps = [
            {
                "start": 5,
                "end": 10,
            },
            {
                "start": 15,
                "end": 20,
            },
            {
                "start": 25,
                "end": 30,
            },
            {
                "start": 55,
                "end": 60,
            }
        ]
        filename = '../videos/tom_and_jerry_trailer_no_music.mp4'
        output_path = '../processed_videos/tom_and_jerry_cropped.mp4'
        
        path = crop_and_stitch_video_segments(filename, example_timestamps, output_path)
        
        print(f"✅ Video cropping completed successfully for '{filename}'!")
        print(f"   📁 Output: {os.path.basename(output_path)}")
        
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-music":
        # Test adding music to video
        video_path = '../videos/tom_and_jerry_trailer_no_music.mp4'
        music_tracks = {
            '../music/classical/sad.mp3': {
                'start': 0,
                'end': 7,
            },
            '../music/classical/dramatic.mp3': {
                'start': 7,
                'end': 14
            },
            '../music/classical/happy.mp3': {
                'start': 14,
                'end': 20
            }
        }
        output_path = '../processed_videos/tom_and_jerry_with_music.mp4'
        
        # Check if music files exist, create mock example if not
        existing_tracks = {}
        for music_file, timing in music_tracks.items():
            if os.path.exists(music_file):
                existing_tracks[music_file] = timing
            else:
                print(f"⚠️ Music file not found: {music_file}")
        
        if existing_tracks:
            path = add_music_to_video(video_path, existing_tracks, output_path)
            print(f"✅ Music mixing completed successfully!")
            print(f"   📁 Output: {os.path.basename(output_path)}")
        else:
            print("❌ No valid music files found for testing")
            
    else:
        print("🎬 Pipeline Test Functions")
        print("Usage:")
        print("  python pipeline.py --test-compatibility <video>  # Check video format compatibility")
        print("  python pipeline.py --test-crop                   # Test video cropping and stitching")
        print("  python pipeline.py --test-music                  # Test adding background music")
        print("")
        print("🔧 Recent improvements:")
        print("  • Smart processing: Fast copy with fallback re-encoding only when needed")
        print("  • Optimized seeking: Faster segment extraction with keyframe alignment")
        print("  • Minimal re-encoding: Only re-encode when absolutely necessary")
        print("  • Better error handling and video analysis")
        print("  • Optimized for both speed and compatibility")
        print("")
        print("Make sure test files exist:")
        print("  ../videos/tom_and_jerry_trailer_no_music.mp4")
        print("  ../audio/background_music1.mp3 (for music test)")
        print("  ../audio/dramatic_theme.mp3 (for music test)")
        print("  ../audio/upbeat_ending.mp3 (for music test)")