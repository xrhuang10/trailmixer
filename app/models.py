from pydantic import BaseModel
from typing import List
from fastapi import UploadFile, File

class VideoUploadRequest(BaseModel):
    files: List[UploadFile] = File(...)

class VideoUploadResponse(BaseModel):
    message: str
    status: str
    filenames: list[str]
    
class VideoStitchRequest(BaseModel):
    filenames: List[str]

class VideoStitchResponse(BaseModel):
    message: str
    status: str
    filename: str
    
class VideoProcessRequest(BaseModel):
    filename: str
    music_style: str
    num_sentiments: int
    num_segments: int
    desired_duration: int

class VideoProcessResponse(BaseModel):
    message: str
    status: str
    filename: str