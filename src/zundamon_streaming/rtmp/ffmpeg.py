"""FFmpeg制御 - 3ストリーム配信対応"""
import subprocess
import threading
import os
import time

def trace_log(message, level="INFO"):
    timestamp = time.time()
    thread_id = threading.current_thread().ident
    print(f"[{timestamp:.3f}][{thread_id}][{level}] {message}")

class FFmpegStreamer:
    def __init__(self):
        self.process = None
    
    def start_3stream(self, base_pattern: str, mouth_pattern: str, eyes_pattern: str, 
                     rtmp_url: str, fps: int = 30) -> bool:
        """3ストリーム合成配信"""
        
        cmd = [
            "ffmpeg",
            "-re", "-stream_loop", "-1", "-framerate", str(fps), "-start_number", "0", "-i", base_pattern,
            "-re", "-stream_loop", "-1", "-framerate", str(fps), "-start_number", "0", "-i", mouth_pattern,
            "-re", "-stream_loop", "-1", "-framerate", str(fps), "-start_number", "0", "-i", eyes_pattern,
            "-filter_complex", "[0:v][1:v]overlay[temp];[temp][2:v]overlay[outv]",
            "-map", "[outv]",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-f", "flv", rtmp_url
        ]
        
        trace_log("3ストリーム配信開始")
        trace_log(f"ベース: {base_pattern}")
        trace_log(f"口: {mouth_pattern}")
        trace_log(f"目: {eyes_pattern}")
        trace_log(f"FFmpeg command: {' '.join(cmd)}")
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # エラー出力監視
        def monitor_stderr():
            try:
                for line in self.process.stderr:
                    print(f"FFmpeg ERROR: {line.strip()}")
            except:
                pass
        
        # 標準出力監視
        def monitor_stdout():
            try:
                for line in self.process.stdout:
                    print(f"FFmpeg OUT: {line.strip()}")
            except:
                pass
        
        threading.Thread(target=monitor_stderr, daemon=True).start()
        threading.Thread(target=monitor_stdout, daemon=True).start()
        
        return True
    
    def start_stream(self, background_video: str, frames_pattern: str, 
                    rtmp_url: str, fps: int = 30) -> bool:
        """従来の単一ストリーム配信（互換性用）"""
        
        if not background_video:
            cmd = [
                "ffmpeg",
                "-re", "-stream_loop", "-1",
                "-framerate", str(fps), "-start_number", "0", "-i", frames_pattern,
                "-c:v", "libx264", "-preset", "ultrafast",
                "-f", "flv", rtmp_url
            ]
        else:
            if not os.path.exists(background_video):
                trace_log(f"背景動画が見つかりません: {background_video}", "ERROR")
                return False
            
            cmd = [
                "ffmpeg",
                "-re", "-stream_loop", "-1", "-i", background_video,
                "-framerate", str(fps), "-start_number", "0", "-i", frames_pattern,
                "-filter_complex", "[0:v][1:v]overlay[outv]",
                "-map", "[outv]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-f", "flv", rtmp_url
            ]
        
        trace_log(f"FFmpeg command: {' '.join(cmd)}")
        trace_log("単一ストリーム配信開始")
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        def monitor_stderr():
            try:
                for line in self.process.stderr:
                    print(f"FFmpeg ERROR: {line.strip()}")
            except:
                pass
        
        def monitor_stdout():
            try:
                for line in self.process.stdout:
                    print(f"FFmpeg OUT: {line.strip()}")
            except:
                pass
        
        threading.Thread(target=monitor_stderr, daemon=True).start()
        threading.Thread(target=monitor_stdout, daemon=True).start()
        
        return True
    
    def stop(self):
        """FFmpegプロセス停止"""
        if self.process:
            trace_log("FFmpeg停止開始")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                trace_log("FFmpeg強制終了", "WARN")
                self.process.kill()
            self.process = None
            trace_log("FFmpeg停止完了")