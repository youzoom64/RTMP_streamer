# debug_streaming.py
import subprocess
import time
from streamer import VoiceVoxStreamer

def debug_ffmpeg_rtmp():
    """FFmpegのRTMP配信を詳細デバッグ"""
    streamer = VoiceVoxStreamer()
    
    if not streamer.start_rtmp_server():
        return
    
    time.sleep(3)
    
    print("📡 FFmpeg RTMP配信デバッグ...")
    
    # 詳細ログ付きでテストパターン配信
    cmd = [
        'ffmpeg', 
        '-loglevel', 'verbose',  # 詳細ログ
        '-f', 'lavfi', '-i', 'testsrc=duration=15:size=640x480:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=15',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-c:a', 'aac', '-ar', '44100',
        '-f', 'flv', 'rtmp://localhost:1935/live/test-stream'
    ]
    
    print("配信開始（15秒間）...")
    print("別のターミナルでVLCを開いて rtmp://localhost:1935/live/test-stream を試してください")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        
        print("\n=== FFmpeg ログ ===")
        print("Return code:", result.returncode)
        print("\nSTDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        
        if "rtmp://localhost:1935/live/test-stream" in result.stderr:
            print("✅ RTMP接続が確認されました")
        else:
            print("❌ RTMP接続エラーが発生した可能性があります")
            
    except subprocess.TimeoutExpired:
        print("⏰ 配信タイムアウト")
    except Exception as e:
        print(f"❌ エラー: {e}")
    finally:
        streamer.stop_rtmp_server()

if __name__ == "__main__":
    debug_ffmpeg_rtmp()