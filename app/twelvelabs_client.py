import os
from typing import Optional

from dotenv import load_dotenv

from twelvelabs import TwelveLabs
from twelvelabs.models import GenerateOpenEndedTextResult
from twelvelabs.models.task import Task

load_dotenv()

# Twelve Labs configuration
TWELVE_LABS_API_KEY = os.getenv("TWELVE_LABS_API_KEY")
if not TWELVE_LABS_API_KEY:
    raise ValueError("TWELVE_LABS_API_KEY is not set")

TWELVE_LABS_INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")
if not TWELVE_LABS_INDEX_ID:
    raise ValueError("TWELVE_LABS_INDEX_ID is not set")

twelve_labs_client = TwelveLabs(api_key=TWELVE_LABS_API_KEY)

def upload_video_to_twelvelabs(file_path: str) -> Optional[str]:
    """
    Upload a video to Twelve Labs for indexing.
    
    Args:
        file_path: Local path to the video file
        filename: Original filename for reference
        
    Returns:
        video_id if successful, None if failed
    """
    
    try:
        # Create a video indexing task
        assert TWELVE_LABS_INDEX_ID is not None  # Type hint for linter
        
        task = twelve_labs_client.task.create(
            index_id=TWELVE_LABS_INDEX_ID,
            file=file_path
        )
        
        print(f"Created Twelve Labs task: {task.id}")
        
        # Wait for the task to complete with status updates
        def on_task_update(task: Task):
            print(f"Twelve Labs Status: {task.status}")
        
        # Hang until the task is done
        task.wait_for_done(callback=on_task_update)
        
        if task.status == "ready":
            print(f"Video successfully indexed. Video ID: {task.video_id}")
            return task.video_id
        else:
            raise RuntimeError(f"Twelve Labs indexing failed with status: {task.status}")
            
    except Exception as e:
        print(f"Error uploading to Twelve Labs: {str(e)}")
        raise e
    
def prompt_twelvelabs(video_id: str, prompt: str) -> Optional[GenerateOpenEndedTextResult]:
    """
    Prompt Twelve Labs for a video.
    
    Args:
        video_id: The ID of the video to prompt
        prompt: The prompt to send to Twelve Labs
        
    Returns:
        The response from Twelve Labs
    """
    try:
        print(f"Prompting Twelve Labs with video ID: {video_id} ")
        response = twelve_labs_client.analyze(
            video_id=video_id,
            prompt=prompt
        )
        print(f"Prompting ended")
        return response
    except Exception as e:
        print(f"Error prompting Twelve Labs: {str(e)}")
        raise e

# For testing
if __name__ == "__main__":
    # upload_video_to_twelvelabs("..\\files\\speed.mp4")
    print(prompt_twelvelabs("687b0e4861acc759544004a1", "What is going on in this video?"))