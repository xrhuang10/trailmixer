from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip
from paths import UPLOAD_DIR, STITCHED_DIR, CROPPED_DIR, PROCESSED_DIR
from typing import List

def stitch_videos(filepaths: list[str], output_filename: str) -> str:
    try:
        videos = [VideoFileClip(filepath) for filepath in filepaths]
        final_video = concatenate_videoclips(videos)
        final_video.write_videofile(STITCHED_DIR / output_filename)
        
        for video in videos:
            video.close()
        final_video.close()
        
        return STITCHED_DIR / output_filename
    except Exception as e:
        raise Exception(f"Error stitching videos: {e}")

def crop_video(input_path: str, segments: List[dict], output_filename: str) -> str:
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
        with VideoFileClip(input_path) as video:
            for segment in segments:
                start = float(segment['start'])
                end = float(segment['end'])
                clip = video.subclipped(start, end)
                temp_clips.append(clip)
            # Concatenate all segments
            output_path = CROPPED_DIR / output_filename
            final_clip = concatenate_videoclips(temp_clips, method="compose")
            final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
            final_clip.close()
        # Close all temp clips
        for clip in temp_clips:
            clip.close()
        return output_path
    finally:
        # Clean up temp clips if needed (MoviePy handles most cleanup)
        pass

def apply_music(input_path: str, segments: List[dict], output_filename: str) -> str:
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
        with VideoFileClip(input_path) as video:
            for segment in segments:
                start = float(segment['start'])
                end = float(segment['end'])
                song_path = segment['song_path']
                
                # Extract the video segment
                video_clip = video.subclipped(start, end)
                
                # Load the audio file
                audio_clip = AudioFileClip(song_path)
                
                # Trim audio to match video duration
                audio_clip = audio_clip.subclipped(0, video_clip.duration)
                
                # Set the audio of the video clip
                video_clip = video_clip.set_audio(audio_clip)
                
                temp_clips.append(video_clip)
            
            # Concatenate all segments
            output_path = PROCESSED_DIR / output_filename
            final_clip = concatenate_videoclips(temp_clips, method="compose")
            final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
            final_clip.close()
            
        # Close all temp clips
        for clip in temp_clips:
            clip.close()
            
        return output_path
    except Exception as e:
        raise Exception(f"Error applying music to video: {e}")
    finally:
        # Clean up temp clips if needed
        for clip in temp_clips:
            try:
                clip.close()
            except:
                pass

if __name__ == "__main__":
    time_segments = [{'start': 0.0, 'end': 7.0}, {'start': 14.0, 'end': 20.0}]
    filepaths = [UPLOAD_DIR / "speed.mp4", UPLOAD_DIR / "speed copy.mp4"]
    crop_video(filepaths[0], time_segments, "cropped_video.mp4")