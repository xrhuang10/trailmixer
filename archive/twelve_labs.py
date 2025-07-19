import os

from dotenv import load_dotenv

from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

# Debug: Check current directory and .env file
print(f"Current working directory: {os.getcwd()}")
print(f".env file exists: {os.path.exists('.env')}")

load_dotenv()

TL_API_KEY = os.getenv("TL_API_KEY")
print(f"TL_API_KEY value: {TL_API_KEY}")

if not TL_API_KEY:
    raise ValueError("TL_API_KEY is None. Please check your .env file.")

print(f"API Key loaded: {TL_API_KEY[:10]}...")

client = TwelveLabs(api_key=TL_API_KEY)

task = client.task.create(
  index_id="687b0231c5994cb471747aba",
  file="videos/tom_and_jerry_trailer_no_music.mp4"
)
print(f"Task id={task.id}")
# Utility function to print the status of a video indexing task
def on_task_update(task: Task):
      print(f"  Status={task.status}")
task.wait_for_done(sleep_interval=5, callback=on_task_update)
if task.status != "ready":
  raise RuntimeError(f"Indexing failed with status {task.status}")
print(f"Video ID: {task.video_id}")