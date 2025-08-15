from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip
from moviepy.audio.fx import MultiplyVolume
from paths import UPLOAD_DIR, STITCHED_DIR, CROPPED_DIR, PROCESSED_DIR, MUSIC_DIR, VIDEOS_DIR
from typing import List
from pathlib import Path
import os
from utils import _to_seconds


def stitch_videos(filepaths: list[Path], output_filename: str = None) -> Path:
    try:
        videos = [VideoFileClip(str(filepath)) for filepath in filepaths]
        if output_filename is None:
            output_filename = f"stitched_{filepaths[0].stem}.mp4"
        output_path = STITCHED_DIR / output_filename
        final_video = concatenate_videoclips(videos)
        final_video.write_videofile(str(output_path))
        for video in videos:
            video.close()
        final_video.close()
        return output_path
    except Exception as e:
        raise Exception(f"Error stitching videos: {e}")

def sanitize_segments(segments, video_duration: float):
    """Clamp to [0, duration], drop invalid ranges, and sort."""
    cleaned = []
    for seg in segments:
        start = max(0.0, min(float(seg["start"]), video_duration))
        end   = max(0.0, min(float(seg["end"]),   video_duration))
        if end > start:  # keep only positive-length segments
            cleaned.append({"start": start, "end": end})
    cleaned.sort(key=lambda s: s["start"])
    return cleaned


def crop_video(input_path: Path, segments: List[dict], output_filename: str = None) -> Path:
    """
    Crops a video into segments and stitches them back together.
    Args:
        input_path: Path to the input video file.
        segments: List of dicts with 'start' and 'end' keys (float seconds) for each segment.
        output_path: Optional path to save the stitched video. If None, a tempfile is used.
    Returns:
        Path to the stitched video file.
    """
    temp_clips = []
    try:
        with VideoFileClip(str(input_path)) as video:
            duration = float(video.duration)
            safe_segments = sanitize_segments(segments, duration)
            if not safe_segments:
                raise ValueError(
                    f"No valid segments within duration={duration:.2f}s. Raw={segments!r}"
                )

            for segment in safe_segments:
                start = float(segment['start'])
                end = float(segment['end'])
                clip = video.subclipped(start, end)
                temp_clips.append(clip)
            if output_filename is None:
                output_filename = f"cropped_{input_path.stem}.mp4"
            output_path = PROCESSED_DIR / output_filename
            final_clip = concatenate_videoclips(temp_clips, method="compose")
            final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
            final_clip.close()
        for clip in temp_clips:
            clip.close()
        return output_path
    finally:
        # Clean up temp clips if needed (MoviePy handles most cleanup)
        pass

# def apply_music(input_path: Path, segments: List[dict], output_filename: str = None) -> Path:
#     """
#     Applies music to video segments based on start, end, and song_path.
#     Args:
#         input_path: Path to the input video file.
#         segments: List of dicts with 'start', 'end', and 'song_path' keys.
#         output_filename: Name of the output video file.
#     Returns:
#         Path to the output video file with music applied.
#     """
#     temp_clips = []
#     try:
#         with VideoFileClip(str(input_path)) as video:
#             for segment in segments:
#                 start = float(segment['start'])
#                 end = float(segment['end'])
#                 song_path = segment['song_path']
                
#                 # Extract the video segment
#                 video_clip = video.subclipped(start, end)
                
#                 # Load the audio file
#                 audio_clip = AudioFileClip(str(song_path))
                
#                 # Trim audio to match video duration
#                 audio_clip = audio_clip.subclipped(0, video_clip.duration)
                
#                 # Set the volume of the audio clip
#                 audio_clip = audio_clip.with_effects([MultiplyVolume(0.15)])
                
#                 # Set the audio of the video clip
#                 video_clip = video_clip.with_audio(CompositeAudioClip([audio_clip, video_clip.audio]))
                
#                 temp_clips.append(video_clip)
            
#             if output_filename is None:
#                 output_filename = f"music_{input_path.stem}.mp4"
#             output_path = PROCESSED_DIR / output_filename
#             final_clip = concatenate_videoclips(temp_clips, method="compose")
#             final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
#             final_clip.close()
            
#         for clip in temp_clips:
#             clip.close()
            
#         return output_path
#     except Exception as e:
#         raise Exception(f"Error applying music to video: {e}")
#     finally:
#         for clip in temp_clips:
#             try:
#                 clip.close()
#             except:
#                 pass


def _clamp_segments(segments, duration):
    cleaned = []
    for seg in segments:
        start = max(0.0, min(_to_seconds(seg["start"]), duration))
        end   = max(0.0, min(_to_seconds(seg["end"]),   duration))
        if end > start:
            cleaned.append({"start": start, "end": end, "song_path": seg["song_path"]})
    cleaned.sort(key=lambda s: s["start"])
    return cleaned

def apply_music(input_path: Path, segments: List[dict], output_filename: str = None) -> Path:
    """
    Applies music to segments. Each segment dict must have: start, end, song_path.
    """
    temp_clips = []
    final_clip = None
    try:
        with VideoFileClip(str(input_path)) as video:  # keep audio=True (default)
            duration = float(video.duration)
            safe_segments = _clamp_segments(segments, duration)
            if not safe_segments:
                raise ValueError(f"No valid segments within duration={duration:.2f}s. Raw={segments!r}")

            for seg in safe_segments:
                start = seg["start"]
                end   = seg["end"]
                song_path = Path(seg["song_path"])

                if not song_path.exists():
                    raise FileNotFoundError(f"Music file not found: {song_path}")

                # Extract the video segment
                clip = video.subclip(start, end)

                # Prepare background music, trimmed to clip duration and with volume
                music = AudioFileClip(str(song_path)).subclip(0, clip.duration).volumex(0.15)

                # Combine with original audio if present (else just music)
                tracks = []
                if clip.audio is not None:
                    # Reduce original slightly if you want ducking; tweak as needed:
                    tracks.append(clip.audio.volumex(0.8))
                tracks.append(music)

                composite = CompositeAudioClip(tracks)
                clip = clip.set_audio(composite)

                temp_clips.append(clip)

            if output_filename is None:
                output_filename = f"music_{Path(input_path).stem}.mp4"

            output_path = (Path(os.getenv("PROCESSED_DIR", str(PROCESSED_DIR))) / output_filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            final_clip = concatenate_videoclips(temp_clips, method="compose")
            final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
        return output_path
    except Exception as e:
        raise Exception(f"Error applying music to video: {e}")
    finally:
        # Close in reverse creation order to avoid ffmpeg readers lingering
        try:
            if final_clip:
                final_clip.close()
        except Exception:
            pass
        for clip in temp_clips:
            try:
                # This also closes any CompositeAudioClip attached to it
                clip.close()
            except Exception:
                pass


if __name__ == "__main__":
    # Example workflow for apply_music function
    from pathlib import Path
    
    # Define segments with start time, end time, and song path
    segments = [
        {
            'start': 0.0, 
            'end': 10.0, 
            'song_path': MUSIC_DIR / "meme" / "happy.mp3"
        },
        {
            'start': 10.0, 
            'end': 20.0, 
            'song_path': MUSIC_DIR / "meme" / "sad.mp3"
        },
        {
            'start': 20.0, 
            'end': 30.0, 
            'song_path': MUSIC_DIR / "meme" / "dramatic.mp3"
        }
    ]
    
    # Input video file
    input_video = VIDEOS_DIR / "speed.mp4"
    
    # Apply music to video segments
    try:
        output_path = apply_music(input_video, segments, "final_video_with_music.mp4")
        print(f"Video with music applied successfully: {output_path}")
    except Exception as e:
        print(f"Error: {e}")