from fastapi import FastAPI, UploadFile, File

app = FastAPI()

@app.post('/video/upload')
def upload_video(file: UploadFile = File(...)):
    pass

@app.get('/video/processed/{video_filename}')
def get_processed_video(video_filename: str):
    pass

