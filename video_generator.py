import os
import requests
from dotenv import load_dotenv

load_dotenv()

class VideoGenerator:
    def __init__(self):
        self.api_key = os.getenv("HEYGEN_API_KEY")
        self.avatar_id = os.getenv("AVATAR_ID")
        self.voice_id = "a4c3c4dcfa194c16b3ebdcae567f5b80"  # Provided by user
        if not self.api_key or not self.avatar_id:
            raise ValueError("HEYGEN_API_KEY or AVATAR_ID not found in .env")
        self.base_url = "https://api.heygen.com/v1"

    def upload_to_gofile(self, file_path):
        # Step 1: Get GoFile server (v2)
        server_resp = requests.get('https://api.gofile.io/v2/getServer')
        if server_resp.status_code != 200:
            print(f'[ERROR] GoFile getServer failed. Status: {server_resp.status_code}')
            print(f'[ERROR] Raw response: {server_resp.text}')
            raise Exception('GoFile getServer failed')
        server = server_resp.json()['data']['server']
        # Step 2: Upload file
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            upload_url = f'https://{server}.gofile.io/uploadFile'
            resp = requests.post(upload_url, files=files)
        if resp.status_code != 200:
            print(f'[ERROR] GoFile upload failed. Status: {resp.status_code}')
            print(f'[ERROR] Raw response: {resp.text}')
            raise Exception('GoFile upload failed')
        file_url = resp.json()['data']['downloadPage']
        print(f'[INFO] Uploaded audio to GoFile: {file_url}')
        return file_url

    def generate_video(self, script_path, audio_path, output_file="media/output_video.mp4"):
        # Read script
        with open(script_path, "r", encoding="utf-8") as f:
            script = f.read()
        # Step 1: Upload audio to GoFile.io
        audio_url = self.upload_to_gofile(audio_path)

        # Step 2: Request video generation
        video_url = f"{self.base_url}/video/generate"
        payload = {
            "avatar_id": self.avatar_id,
            "voice_id": self.voice_id,
            "script": script,
            "audio_url": audio_url,
            "lip_sync": True,
            "resolution": "1080p"
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(video_url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Video generation request failed: {response.text}")
        video_task_id = response.json().get("data", {}).get("task_id")
        if not video_task_id:
            raise Exception(f"Video generation did not return a task_id: {response.text}")

        # Step 3: Poll for video completion
        status_url = f"{self.base_url}/video/status/{video_task_id}"
        import time
        for _ in range(60):  # Poll up to 5 minutes
            status_resp = requests.get(status_url, headers=headers)
            if status_resp.status_code != 200:
                raise Exception(f"Failed to get video status: {status_resp.text}")
            status_data = status_resp.json().get("data", {})
            if status_data.get("status") == "completed":
                video_download_url = status_data.get("video_url")
                break
            elif status_data.get("status") == "failed":
                raise Exception(f"Video generation failed: {status_data}")
            time.sleep(5)
        else:
            raise TimeoutError("Video generation timed out.")

        # Step 4: Download the video
        video_resp = requests.get(video_download_url)
        if video_resp.status_code != 200:
            raise Exception(f"Failed to download video: {video_resp.text}")
        with open(output_file, "wb") as f:
            f.write(video_resp.content)
        print(f"[SUCCESS] Video saved to {output_file}")
        return output_file
