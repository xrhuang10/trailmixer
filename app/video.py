from moviepy import VideoFileClip, concatenate_videoclips
from paths import UPLOAD_DIR, OUTPUT_DIR

def stitch_videos(filepaths: list[str]) -> str:
    try:
        videos = [VideoFileClip(filepath) for filepath in filepaths]
        final_video = concatenate_videoclips(videos)
        final_video.write_videofile("output/stitched_video.mp4")
        
        for video in videos:
            video.close()
        final_video.close()
        
        return OUTPUT_DIR / "stitched_video.mp4"
    except Exception as e:
        raise Exception(f"Error stitching videos: {e}")
    
if __name__ == "__main__":
    filepaths = [UPLOAD_DIR / "speed.mp4", UPLOAD_DIR / "speed copy.mp4"]
    stitch_videos(filepaths)