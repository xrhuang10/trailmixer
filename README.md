# 🧠 TrailMixer – AI-Powered Video Trailer Generator

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-orange.svg)](https://ffmpeg.org)
[![TwelveLabs](https://img.shields.io/badge/TwelveLabs-API-purple.svg)](https://twelvelabs.io)

> **Transform raw footage into attention-grabbing trailers in seconds with AI-powered content analysis and automated music synchronization.**
>
> FRONT-END REPO: https://github.com/prestonty/Trailmixer-frontend#

## 🚀 Inspiration

In today's hyper-digital world filled with endless content, standing out as a creator means acting fast. With the rise of content creators and the boom in AI-powered automation, the need to generate impactful videos — quickly — is more urgent than ever. That's why we built **TrailMixer**: an AI-assisted video editor that helps creators transform raw footage into attention-grabbing trailers in seconds.

## 🎬 What It Does

TrailMixer allows users to:

- **Upload raw videos** (single or multiple files)
- **Choose a desired trailer duration** (customizable length)
- **Select a music style** (Pop, Classical, Hip Hop, Electronic, Meme, Cinematic)
- **AI-powered analysis** that identifies the most meaningful clips
- **Automated stitching** of polished trailers with background music
- **Sentiment-based music matching** for perfect mood synchronization

## 🛠️ How We Built It

### Tech Stack

**Frontend:**
- React, TypeScript, JavaScript

**Backend:**
- Python 3.8+
- FastAPI (REST API)
- FFmpeg (video/audio processing)
- TwelveLabs API (AI video analysis)

**AI Tools:**
- **TwelveLabs**: Multimodal video analysis via prompt engineering
- **FFmpeg**: Video/audio stitching and processing
- **Custom Prompt Engineering**: Structured JSON output generation

### Architecture Overview (https://miro.com/app/board/uXjVJcA7HWY=/?share_link_id=973269980552)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI        │    │   TwelveLabs    │
│   (React)       │◄──►│   Backend        │◄──►│   AI Analysis   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   FFmpeg         │
                       │   Processing     │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Final Trailer  │
                       │   (MP4)          │
                       └──────────────────┘
```

## 🧩 Core Features

### 1. **Multi-Video Upload & Stitching**
- Upload multiple video files
- Automatic concatenation using FFmpeg
- Seamless transition handling

### 2. **AI-Powered Content Analysis**
- TwelveLabs API integration for video understanding
- Sentiment analysis for mood detection
- Intelligent segment selection based on importance

### 3. **Smart Music Synchronization**
- Dynamic music selection based on video mood
- Multiple music styles: Pop, Classical, Hip Hop, Electronic, Meme, Cinematic
- Automatic timing synchronization

### 4. **Customizable Output**
- Configurable trailer duration
- Multiple audio tracks support
- Crossfade and transition effects

## 📁 Project Structure

```
trailmixer/
├── app/                          # Main application
│   ├── main.py                   # FastAPI server
│   ├── models.py                 # Pydantic data models
│   ├── pipeline.py               # Video processing pipeline
│   ├── video_processor.py        # Video analysis logic
│   ├── ffmpeg_stitch.py          # FFmpeg integration
│   ├── ffmpeg_builder.py         # FFmpeg command builder
│   ├── audio_picker.py           # Music selection logic
│   ├── twelvelabs_client.py      # TwelveLabs API client
│   └── prompts/                  # AI prompt engineering
│       └── extract_info.py       # Video analysis prompts
├── music/                        # Music library
│   ├── pop/                      # Pop music tracks
│   ├── classical/                # Classical music tracks
│   ├── hiphop/                   # Hip Hop music tracks
│   ├── electronic/               # Electronic music tracks
│   ├── meme/                     # Meme music tracks
│   └── cinematic/                # Cinematic music tracks
├── processed_videos/             # Output directory
├── videos/                       # Input video directory
├── requirements.txt              # Python dependencies
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+**
2. **FFmpeg** (must be installed and available in PATH)
3. **TwelveLabs API Key** (sign up at [twelvelabs.io](https://twelvelabs.io))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/trailmixer.git
   cd trailmixer
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Create .env file
   echo "TWELVE_LABS_API_KEY=your_api_key_here" > .env
   ```

5. **Install FFmpeg**
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### Running the Application

1. **Start the FastAPI server**
   ```bash
   cd app
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Example Usage

```python
import requests

# Upload video and get music timestamps
files = {'video_files': open('your_video.mp4', 'rb')}
response = requests.post('http://localhost:8000/api/video/upload', files=files)
job_id = response.json()['job_id']

# Get music timestamps
timestamps = requests.get(f'http://localhost:8000/api/video/timestamps/{job_id}').json()

# Process video with timestamps
process_data = {
    'timestamps': timestamps['videos'][0]['segments'],
    'music_file_paths': timestamps['videos'][0]['music_file_paths']
}
result = requests.post(f'http://localhost:8000/api/video/process/{job_id}', json=process_data)
```

## 🔧 API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/video/upload` | POST | Upload video(s) and get music timestamps |
| `/api/video/process/{job_id}` | POST | Process video with timestamps |
| `/api/video/timestamps/{job_id}` | GET | Get music timestamps for job |
| `/api/video/status/{job_id}` | GET | Get processing status |
| `/api/video/download/{job_id}` | GET | Download processed video |
| `/health` | GET | Health check |

### Request/Response Examples

**Upload Video:**
```bash
curl -X POST "http://localhost:8000/api/video/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "video_files=@your_video.mp4"
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "music_file_paths": {
    "track1": {
      "file_path": "music/pop/happy.mp3",
      "start_time": 0,
      "end_time": 30
    }
  }
}
```

## 🧩 Challenges We Faced

### 1. **Prompt Engineering Complexity**
- **Challenge**: TwelveLabs doesn't support strict JSON output structures
- **Solution**: Embedded structured JSON schema within prompts and iteratively refined prompt rules
- **Result**: Reliable, structured output for video analysis

### 2. **FFmpeg Integration**
- **Challenge**: Stitching clips via Python wrappers had edge cases and limited documentation
- **Solution**: Extensive research and custom workarounds for cross-platform compatibility
- **Result**: Robust video processing pipeline

### 3. **API Rate Limits**
- **Challenge**: TwelveLabs enforces a 50-request rate limit per API key
- **Solution**: Generated multiple keys in advance and coordinated usage via shared Discord channel and collaborative Google Doc
- **Result**: Scalable API usage management

## ✅ Accomplishments We're Proud Of

- **Rapid Learning**: Quickly learned and integrated new tools like TwelveLabs API and FFmpeg
- **Full-Stack Development**: Designed and implemented a complete product — frontend, backend, AI, media processing — in short timeframe
- **Product Workflow**: Created complete product workflow in Miro, from ideation to deployment
- **AI Integration**: Successfully integrated multimodal AI analysis for video content understanding

## 📚 What We Learned

- **Multimodal Media Processing**: Gained hands-on experience working with video, audio, and sentiment analysis
- **Prompt Engineering**: Discovered that prompt engineering is more nuanced than expected — there's much more to explore: few-shot prompting, tool use enforcement, RAG, and even fine-tuning
- **API Management**: Learned effective strategies for managing API rate limits and coordinating team usage

## 🌱 What's Next for TrailMixer

### 🎵 **Enhanced Audio Features**
- **Sound Effects**: Layer dramatic audio cues over key trailer moments
- **External Music Integration**: Currently uses static library — next step is to dynamically pull music from external APIs based on style, emotion, and tempo

### 🎬 **Advanced Video Processing**
- **Custom Transitions**: Add more sophisticated video transitions between segments
- **Video Effects**: Implement filters, overlays, and visual enhancements
- **Batch Processing**: Support for processing multiple videos simultaneously

### 🤖 **AI Improvements**
- **Fine-tuned Models**: Custom training for better video understanding
- **RAG Integration**: Retrieval-augmented generation for better context
- **Real-time Processing**: Stream processing for live video feeds

### 🌐 **Platform Features**
- **User Management**: Multi-user support with authentication
- **Cloud Storage**: Integration with cloud storage providers
- **Mobile App**: Native mobile application for on-the-go editing

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **TwelveLabs** for providing the AI video analysis capabilities
- **FFmpeg** for the robust video processing tools
- **FastAPI** for the excellent web framework
- **Our Team** for the collaborative effort in building this project

## 📞 Contact

- **Project Link**: [https://github.com/yourusername/trailmixer](https://github.com/yourusername/trailmixer)
- **Issues**: [https://github.com/yourusername/trailmixer/issues](https://github.com/yourusername/trailmixer/issues)

---

**Made with ❤️ by the TrailMixer Team**

*Transform your content creation workflow with AI-powered video editing.*
