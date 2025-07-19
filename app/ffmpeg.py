import ffmpeg  # type: ignore
from models import FfmpegRequest, InputSegment
from typing import List, Tuple, Optional
import os

def _time_to_seconds(time_str: str) -> float:
    """Convert time string (HH:MM:SS or HH:MM:SS.mmm) to seconds."""
    if not time_str:
        return 0.0
    
    parts = time_str.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    else:
        return float(time_str)

def build_input_stream(segment: InputSegment, index: int):
    """Builds the input stream with filters applied based on segment options."""
    input_kwargs = {}

    # Handle clip selection from input file
    clip_start_seconds = _time_to_seconds(segment.clip_start or "00:00:00")
    clip_end_seconds = _time_to_seconds(segment.clip_end or "23:59:59")
    clip_duration = clip_end_seconds - clip_start_seconds

    if segment.clip_start:
        input_kwargs['ss'] = segment.clip_start
    if segment.clip_end:
        input_kwargs['t'] = str(clip_duration)

    # Create base input stream
    base_stream = ffmpeg.input(segment.file_path, **input_kwargs)
    
    # Create stream based on type
    if segment.file_type == 'audio':
        stream = base_stream.audio
        # Apply audio filters
        if segment.volume and segment.volume != 1.0:
            stream = ffmpeg.filter(stream, 'volume', segment.volume)
        if segment.fade_in:
            stream = ffmpeg.filter(stream, 'afade', t='in', st=0, d=segment.fade_in)
        if segment.fade_out:
            # Calculate fade out start time based on duration
            fade_out_seconds = _time_to_seconds(segment.fade_out)
            fade_start = clip_duration - fade_out_seconds
            stream = ffmpeg.filter(stream, 'afade', t='out', st=fade_start, d=segment.fade_out)
        
        # Handle placement timing
        start_seconds = _time_to_seconds(segment.start_time)
        if start_seconds > 0:
            # Add silence before the audio to place it at the right time
            stream = ffmpeg.filter(stream, 'adelay', f'{int(start_seconds * 1000)}|{int(start_seconds * 1000)}')

    elif segment.file_type == 'video':
        stream = base_stream.video
        # Apply video filters
        if segment.fade_in:
            stream = ffmpeg.filter(stream, 'fade', t='in', st=0, d=segment.fade_in)
        if segment.fade_out:
            # Calculate fade out start time based on duration
            fade_out_seconds = _time_to_seconds(segment.fade_out)
            fade_start = clip_duration - fade_out_seconds
            stream = ffmpeg.filter(stream, 'fade', t='out', st=fade_start, d=segment.fade_out)

    return stream

def stitch_ffmpeg_request(request: FfmpegRequest) -> str:
    """Stitch multiple video and audio segments together using FFmpeg."""
    audio_streams = []
    video_streams = []

    # Build input streams
    for i, segment in enumerate(request.input_segments):
        stream = build_input_stream(segment, i)
        if segment.file_type == 'audio':
            audio_streams.append(stream)
        elif segment.file_type == 'video':
            # For video type, handle both video and audio streams
            video_streams.append(stream)
            if segment.volume and segment.volume > 0:  # Only add audio if volume > 0
                # Get audio stream from the same input
                audio_kwargs = {}
                if segment.clip_start:
                    audio_kwargs['ss'] = segment.clip_start
                if segment.clip_end:
                    clip_start_seconds = _time_to_seconds(segment.clip_start or "00:00:00")
                    clip_end_seconds = _time_to_seconds(segment.clip_end)
                    audio_kwargs['t'] = str(clip_end_seconds - clip_start_seconds)
                
                audio_stream = ffmpeg.input(segment.file_path, **audio_kwargs).audio
                if segment.volume != 1.0:
                    audio_stream = ffmpeg.filter(audio_stream, 'volume', segment.volume)
                audio_streams.append(audio_stream)

    # Process audio streams
    final_audio = None
    if audio_streams:
        if len(audio_streams) > 1:
            # Mix multiple audio streams
            final_audio = ffmpeg.filter(audio_streams, 'amix', inputs=len(audio_streams), duration='longest')
        else:
            final_audio = audio_streams[0]

        # Apply global audio settings
        if request.global_volume and request.global_volume != 1.0:
            final_audio = ffmpeg.filter(final_audio, 'volume', request.global_volume)

        if request.normalize_audio:
            final_audio = ffmpeg.filter(final_audio, 'dynaudnorm')

    # Process video streams
    final_video = None
    if video_streams:
        if len(video_streams) > 1:
            # For multiple videos, we'll use a simpler approach
            # Note: In a real implementation, you might want to use filter_complex
            # For now, we'll take the first video and apply filters
            final_video = video_streams[0]
            # TODO: Implement proper video concatenation using filter_complex
        else:
            final_video = video_streams[0]

        # Apply video filters
        if request.scale:
            final_video = ffmpeg.filter(final_video, 'scale', request.scale)
        if request.fps:
            final_video = ffmpeg.filter(final_video, 'fps', fps=request.fps)

    # Build output options
    output_kwargs = {
        'vcodec': request.video_codec,
        'acodec': request.audio_codec,
        'preset': request.preset
    }

    if request.crf is not None:
        output_kwargs['crf'] = request.crf
    if request.video_bitrate:
        output_kwargs['b:v'] = request.video_bitrate
    if request.audio_bitrate:
        output_kwargs['b:a'] = request.audio_bitrate
    if request.audio_channels:
        output_kwargs['ac'] = request.audio_channels
    if request.audio_sample_rate:
        output_kwargs['ar'] = request.audio_sample_rate
    if request.quiet:
        output_kwargs['loglevel'] = 'quiet'

    # Create output stream based on what streams we have
    if final_video and final_audio:
        # Combined video and audio
        output = ffmpeg.output(final_video, final_audio, request.output_file, **output_kwargs)
    elif final_video:
        # Video only
        output_kwargs['an'] = None  # Disable audio
        output = ffmpeg.output(final_video, request.output_file, **output_kwargs)
    elif final_audio:
        # Audio only
        output_kwargs['vn'] = None  # Disable video
        output = ffmpeg.output(final_audio, request.output_file, **output_kwargs)
    else:
        raise RuntimeError("No input streams available")

    if request.overwrite:
        output = output.overwrite_output()

    if request.progress:
        output = output.global_args('-progress', 'pipe:1')

    # Run the command
    try:
        output.run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        stdout_msg = e.stdout.decode() if e.stdout else ""
        raise RuntimeError(f"FFmpeg failed:\nSTDERR:\n{error_msg}\nSTDOUT:\n{stdout_msg}")

    return request.output_file
