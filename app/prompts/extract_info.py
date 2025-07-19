import json

with open("prompts/twelvelabs_output_schema.json", "r") as f:
    twelvelabs_output_schema = json.load(f)

extract_info_prompt = f"""
You are a helpful assistant that extracts information from a video.

You will be given a video and a prompt.

You will need to extract the information from the video and return it in a structured format.

Given the following video, please extract the following information and return it in a structured JSON format.

Information to extract:
- Video ID
- Video title
- Video description
- Video length
- Overall Mood
- List of timestamps
- Sentiment of timestamp
- Song name
- Song start timestamp
- Song end timestamp

Please generate a song name and its song timestamp based on the overall mood of the video and the sentiment of the timestamp.
Feel free to choose any song.

The JSON must follow the following format:
{json.dumps(twelvelabs_output_schema, indent=4)}

Do not include any other text in your response. ONLY return the JSON.


"""

