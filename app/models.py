from pydantic import BaseModel

class TwelveLabsResponse(BaseModel):
    pass

class FfmpegRequest(BaseModel):
    start_time: str