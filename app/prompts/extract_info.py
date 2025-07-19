import json

with open("prompts/twelvelabs_output_schema.json", "r") as f:
    twelvelabs_output_schema = json.load(f)

extract_info_prompt = f"""
You are a professional video analyst that extracts information from videos for automated music mixing and editing.

You will be given a video and need to analyze it to extract timing and mood information that will be used to automatically add appropriate background music.

Analyze the video and extract the following information in structured JSON format:

**Video Information:**
- Video ID, title, description, and length
- Overall mood of the entire video

**Segment Analysis:**
- Break the video into logical segments based on mood/content changes. Don't change it too often, it should change every scene or at a clear mood switch, not every 5 seconds.
- For each segment, identify:
  - Start and end times (in seconds only, as numbers)
  - Sentiment/mood of that specific segment
  - Recommended music style/genre that would complement the segment
  - Intensity level (low/medium/high)

**Important Guidelines:**
- Timestamps must be numeric values in seconds (e.g., 15.5, not "15s" or "00:15")
- Music styles should be practical genres/styles (e.g., "upbeat electronic", "soft acoustic", "cinematic orchestral") 
- DO NOT suggest specific copyrighted songs or artist names
- Focus on mood-appropriate music categories that can be sourced legally
- Segments should cover the entire video duration without gaps or overlaps

Return ONLY the JSON response following this exact format:
{json.dumps(twelvelabs_output_schema, indent=4)}

Do not include any other text in your response. ONLY return the JSON.
"""

