import os

from dotenv import load_dotenv

from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

load_dotenv()

TL_API_KEY = os.getenv('TL_API_KEY')
client = TwelveLabs(api_key=TL_API_KEY)

task = client.task.create(
  index_id=<"<YOUR_INDEX_ID>",
  file="<YOUR_FILE_PATH>"
)
print(f"Task id={task.id}")
# Utility function to print the status of a video indexing task
def on_task_update(task: Task):
      print(f"  Status={task.status}")
task.wait_for_done(sleep_interval=5, callback=on_task_update)
if task.status != "ready":
  raise RuntimeError(f"Indexing failed with status {task.status}")
print(f"Video ID: {task.video_id}")