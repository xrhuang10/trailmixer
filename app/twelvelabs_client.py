import os
import sys
import json
from typing import Optional, Dict, Any
import datetime

# Add the project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

from twelvelabs import TwelveLabs
from twelvelabs.models import GenerateOpenEndedTextResult
from twelvelabs.models.task import Task
from prompts.extract_info import extract_info_prompt

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
        print(f"Prompting Twelve Labs with video ID: {video_id}")
        
        response = twelve_labs_client.analyze(
            video_id=video_id,
            prompt=prompt
        )
        print(f"Prompting complete! Response received.")
        return response
    except Exception as e:
        print(f"Error prompting Twelve Labs: {str(e)}")
        raise e  # Re-raise the exception so the caller can handle it

def clean_llm_string_output_to_json(string: str) -> Dict[str, Any]:
    """
    Convert a string to a JSON object, cleaning markdown formatting if present.
    
    Args:
        string: The raw response string from the LLM
        
    Returns:
        Parsed JSON as a dictionary
    """
    # Remove leading/trailing whitespace
    cleaned = string.strip()
    
    # Remove markdown code block formatting
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]  # Remove "```json"
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]  # Remove "```"
    
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]  # Remove trailing "```"
    
    # Remove any remaining leading/trailing whitespace
    cleaned = cleaned.strip()
    
    # Parse the cleaned JSON
    return json.loads(cleaned)

def export_to_json_file(cleaned_data: Dict[str, Any], filename: str) -> str:
    """
    Export the cleaned data to a JSON file.
    
    Args:
        cleaned_data: The cleaned response data
        filename: Optional filename. If None, will generate one based on video_id and timestamp
        
    Returns:
        The path to the exported JSON file
    """
    # Ensure filename has .json extension
    if not filename.endswith('.json'):
        filename += '.json'
    
    # Create llm_answers directory if it doesn't exist
    output_dir = "llm_answers"
    os.makedirs(output_dir, exist_ok=True)
    
    # Full path for the file
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON exported successfully to: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Error exporting to JSON: {e}")
        return ""

# For testing
if __name__ == "__main__":
    # upload_video_to_twelvelabs("..\\files\\speed.mp4")
    response = prompt_twelvelabs("687bb8d061fa6d2e4d153aaa", extract_info_prompt)
    if response:
        # Get cleaned data
        
        cleaned_json = clean_llm_string_output_to_json(response.data)
        print(f"Cleaned JSON: {cleaned_json}")
        video_title = cleaned_json["video_title"]
        
        # Use timestamp_video_id format instead of video title to avoid special characters
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        video_id = "687bb8d061fa6d2e4d153aaa"  # Use actual video_id from the test
        exported_file = export_to_json_file(cleaned_json, f"{timestamp}_{video_id}.json")
        if exported_file:
            print(f"📁 File saved to: {exported_file}")