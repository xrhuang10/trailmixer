from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip
from moviepy.audio.fx import MultiplyVolume
from paths import UPLOAD_DIR, STITCHED_DIR, CROPPED_DIR, PROCESSED_DIR, MUSIC_DIR, VIDEOS_DIR
from typing import List
from pathlib import Path

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
            for segment in segments:
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

def apply_music(input_path: Path, segments: List[dict], output_filename: str = None) -> Path:
    """
    Applies music to video segments based on start, end, and song_path.
    Args:
        input_path: Path to the input video file.
        segments: List of dicts with 'start', 'end', and 'song_path' keys.
        output_filename: Name of the output video file.
    Returns:
        Path to the output video file with music applied.
    """
    temp_clips = []
    try:
        with VideoFileClip(str(input_path)) as video:
            for segment in segments:
                start = float(segment['start'])
                end = float(segment['end'])
                song_path = segment['song_path']
                
                # Extract the video segment
                video_clip = video.subclipped(start, end)
                
                # Load the audio file
                audio_clip = AudioFileClip(str(song_path))
                
                # Trim audio to match video duration
                audio_clip = audio_clip.subclipped(0, video_clip.duration)
                
                # Set the volume of the audio clip
                audio_clip = audio_clip.with_effects([MultiplyVolume(0.15)])
                
                # Set the audio of the video clip
                video_clip = video_clip.with_audio(CompositeAudioClip([audio_clip, video_clip.audio]))
                
                temp_clips.append(video_clip)
            
            if output_filename is None:
                output_filename = f"music_{input_path.stem}.mp4"
            output_path = PROCESSED_DIR / output_filename
            final_clip = concatenate_videoclips(temp_clips, method="compose")
            final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
            final_clip.close()
            
        for clip in temp_clips:
            clip.close()
            
        return output_path
    except Exception as e:
        raise Exception(f"Error applying music to video: {e}")
    finally:
        for clip in temp_clips:
            try:
                clip.close()
            except:
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