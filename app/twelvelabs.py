import os

from dotenv import load_dotenv

from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

load_dotenv()

TL_API_KEY = os.getenv('TL_API_KEY')
if not TL_API_KEY:
    raise ValueError("TL_API_KEY is not set")

client = TwelveLabs(api_key=TL_API_KEY)

