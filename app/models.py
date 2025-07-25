from pydantic import BaseModel

class VideoUploadResponse(BaseModel):
    message: str
    status: str
    filenames: list[str]
    
class VideoStitchResponse(BaseModel):
    message: str
    status: str
    filename: str