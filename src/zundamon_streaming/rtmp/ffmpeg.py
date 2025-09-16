"""FFmpeg制御"""
import subprocess
import threading
import os

class FFmpegStreamer:
    def __init__(self):
        self.process = None
    
    def start_stream(self, background_video: str, frames_pattern: str, 
                    rtmp_url: str, fps: int = 30) -> bool:
        if not os.path.exists(background_video):
            print(f"背景動画が見つかりません: {background_video}")
            return False
        
        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1", "-i", background_video,
            "-framerate", str(fps), "-start_number", "0", "-i", frames_pattern,
            "-filter_complex", "[0:v][1:v]overlay[outv]",
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-f", "flv", rtmp_url
        ]
        
        print(f"FFmpeg command: {' '.join(cmd)}")
        print("FFmpeg配信開始")
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # ← stderrを分離
            universal_newlines=True
        )
        
        # エラー出力を即座に表示
        def monitor_stderr():
            try:
                for line in self.process.stderr:
                    print(f"FFmpeg ERROR: {line.strip()}")
            except:
                pass
        
        # 標準出力を表示
        def monitor_stdout():
            try:
                for line in self.process.stdout:
                    print(f"FFmpeg OUT: {line.strip()}")
            except:
                pass
        
        threading.Thread(target=monitor_stderr, daemon=True).start()
        threading.Thread(target=monitor_stdout, daemon=True).start()
        
        return True