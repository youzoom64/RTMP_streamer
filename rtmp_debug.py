# rtmp_debug.py
import requests
import socket
import subprocess
import time

def check_rtmp_detailed():
    print("=== RTMP サーバー詳細確認 ===")
    
    # ポート確認
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 1935))
    sock.close()
    
    if result == 0:
        print("✅ ポート1935は開いています")
    else:
        print("❌ ポート1935が開いていません")
        return False
    
    # HTTP管理画面確認
    try:
        response = requests.get("http://localhost:8000", timeout=5)
        print(f"✅ HTTP管理画面: {response.status_code}")
    except:
        print("❌ HTTP管理画面にアクセスできません")
    
    return True

def test_simple_rtmp_push():
    """シンプルなRTMPプッシュテスト"""
    print("=== シンプルRTMPプッシュテスト ===")
    
    # テスト用の短い動画を作成
    cmd_create = [
        'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=5:size=320x240:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=5',
        '-c:v', 'libx264', '-c:a', 'aac', '-t', '5', 'test_input.mp4'
    ]
    
    print("📹 テスト動画作成中...")
    result = subprocess.run(cmd_create, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ テスト動画作成失敗: {result.stderr}")
        return False
    
    # RTMPプッシュテスト
    cmd_push = [
        'ffmpeg', '-re', '-i', 'test_input.mp4',
        '-c', 'copy', '-f', 'flv', 'rtmp://localhost:1935/live/test-stream'
    ]
    
    print("📡 RTMP プッシュテスト中...")
    result = subprocess.run(cmd_push, capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        print("✅ RTMP プッシュ成功")
        return True
    else:
        print(f"❌ RTMP プッシュ失敗: {result.stderr}")
        return False

if __name__ == "__main__":
    check_rtmp_detailed()
    test_simple_rtmp_push()