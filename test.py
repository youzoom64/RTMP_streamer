"""全パーツ個別表示テスト - サーバー接続待機付き"""
import sys
import os
import time
import subprocess
import threading
import socket

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.zundamon_streaming.image.loader import PNGLoader
from src.zundamon_streaming.image.cache import ImageCache
from PIL import Image

def wait_for_rtmp_server(host='localhost', port=1935, timeout=30):
    """RTMPサーバーへの接続を待機"""
    print(f"RTMPサーバー接続待機中 ({host}:{port})")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print("RTMPサーバー接続確認")
                print("5秒後にテスト開始")
                time.sleep(5)
                return True
                
        except:
            pass
        
        time.sleep(1)
    
    print("RTMPサーバー接続タイムアウト")
    return False

def test_all_parts_individually():
    """全パーツを個別に黒背景で配信"""
    
    if not wait_for_rtmp_server():
        return
    
    loader = PNGLoader("assets/zundamon")
    cache = ImageCache()
    
    test_parts = [
        ("素体", "_服装2/_素体_"),
        ("服", "_服装1/_いつもの服_"),
        ("左腕", "_服装1/!左腕/_基本_"),
        ("右腕", "_服装1/!右腕/_基本_"),
        ("眉", "!眉/_普通眉_"),
        ("白目", "!目/_目セット/_普通白目_"),
        ("黒目", "!目/_目セット/!黒目/_普通目_"),
        ("目UU", "!目/_UU_"),
        ("目にっこり", "!目/_にっこり_"),
        ("口むふ", "!口/_むふ_"),
        ("口ほあー", "!口/_ほあー_"),
        ("口ほあ", "!口/_ほあ_"),
        ("口ほー", "!口/_ほー_"),
        ("口お", "!口/_お_"),
        ("枝豆", "!枝豆/_枝豆通常_"),
    ]
    
    os.makedirs("test_individual_frames", exist_ok=True)
    
    frame_no = 0
    
    def create_part_frame(part_name, part_path):
        nonlocal frame_no
        
        canvas = Image.new("RGB", (640, 480), (0, 0, 0))
        
        part_file = loader.find_layer_file(part_path)
        if part_file:
            part_img = cache.get(part_file)
            x = (640 - part_img.width) // 2
            y = (480 - part_img.height) // 2
            canvas.paste(part_img, (x, y), part_img)
            print(f"{part_name}表示: {part_file}")
        else:
            print(f"{part_name}未発見: {part_path}")
            canvas = Image.new("RGB", (640, 480), (255, 0, 0))
        
        frame_path = f"test_individual_frames/part_{frame_no:06d}.png"
        canvas.save(frame_path)
        frame_no += 1
        return frame_path
    
    for part_name, part_path in test_parts:
        print(f"=== {part_name} テスト ===")
        for _ in range(60):
            create_part_frame(part_name, part_path)
    
    cmd = [
        "ffmpeg", "-re", "-framerate", "30", 
        "-i", "test_individual_frames/part_%06d.png",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-f", "flv",
        "rtmp://localhost:1935/live/test-stream"
    ]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    print("全パーツ個別配信開始")
    time.sleep(35)
    
    process.terminate()
    print("テスト完了")

if __name__ == "__main__":
    test_all_parts_individually()