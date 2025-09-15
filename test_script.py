# test_script.py
import os
import subprocess
import time
import threading
import queue
from streamer import VoiceVoxStreamer

def ask_rag(question):
    responses = {
        "天気": "今日は晴れています。気温は25度です。",
        "python": "Pythonは初心者にも優しいプログラミング言語です。",
        "時間": "現在の時刻は午後3時です。",
    }
    
    for key, response in responses.items():
        if key in question.lower():
            return response
    
    return f"「{question}」についてお答えします。AIシステムが正常に動作しています。"

class InteractiveStreamer(VoiceVoxStreamer):
    def __init__(self):
        super().__init__()
        self.question_queue = queue.Queue()
        self.streaming = False
        self.current_process = None
        self.loop_video = None
        self.question_file = "questions.txt"

    def create_simple_video(self, scene_data, audio_file, output_file):
        if not os.path.exists(audio_file):
            return False
        
        background_color = scene_data.get("background_color", "black")
        
        cmd = [
            'ffmpeg', '-y', '-i', audio_file,
            '-f', 'lavfi', '-i', f'color={background_color}:size=1280x720',
            '-map', '1:v', '-map', '0:a',
            '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest', output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def create_scenes_separately(self, script_data, prefix):
        """シーンを個別に作成（親クラスのメソッドを使用）"""
        scenes = script_data.get("scenes", [])
        if not scenes:
            return []
            
        created_scenes = []
        
        for i, scene in enumerate(scenes):
            audio_file = os.path.join(self.audio_dir, f"{prefix}_scene_{i:03d}_audio.wav")
            video_file = os.path.join(self.video_dir, f"{prefix}_scene_{i:03d}_video.mp4")
            
            if not self.generate_voice(scene["text"], scene["speaker_id"], audio_file):
                return []
            
            # 親クラスのメソッドを使用
            if not self.create_character_video(scene, audio_file, video_file):
                return []
            
            created_scenes.append(video_file)
            
        return created_scenes

    def create_loop_video_from_scenes(self, scenes):
        """指定されたシーンからループ動画作成"""
        if not scenes:
            return None
        
        loop_video = "output/loop_stream.mp4"
        concat_list = "loop_concat.txt"
        
        try:
            with open(concat_list, 'w', encoding='utf-8') as f:
                for _ in range(10):
                    for video_file in scenes:
                        abs_path = os.path.abspath(video_file).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")
            
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c:v', 'libx264', '-c:a', 'aac', loop_video
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"ループ動画作成完了: {loop_video}")
                return loop_video
            
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)
        
        return None

    def create_qa_video(self, question, answer):
        """QA動画作成（独立処理）"""
        qa_script = {
            "scenes": [
                {
                    "text": f"質問です。{question}",
                    "speaker_id": 1,
                    "background_color": "darkblue"
                },
                {
                    "text": f"回答します。{answer}",
                    "speaker_id": 1,
                    "background_color": "darkgreen"
                }
            ]
        }
        
        qa_scenes = self.create_scenes_separately(qa_script, "qa")
        if not qa_scenes:
            return None
        
        qa_video = "output/qa_response.mp4"
        concat_list = "qa_concat.txt"
        
        try:
            with open(concat_list, 'w', encoding='utf-8') as f:
                for video_file in qa_scenes:
                    abs_path = os.path.abspath(video_file).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c:v', 'libx264', '-c:a', 'aac', qa_video
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return qa_video if result.returncode == 0 else None
            
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

    def start_stream(self, video_file):
        if not video_file or not os.path.exists(video_file):
            print(f"配信ファイルエラー: {video_file}")
            return False
        
        if self.current_process:
            self.stop_stream()
        
        cmd = [
            'ffmpeg', '-re', '-stream_loop', '-1', '-i', video_file,
            '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv',
            self.rtmp_url
        ]
        
        print(f"配信コマンド: {' '.join(cmd)}")
        
        # stderr を STDOUT に統合してリアルタイム表示
        self.current_process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        self.streaming = True
        
        # FFmpegの出力を別スレッドで監視
        def monitor_ffmpeg():
            try:
                for line in self.current_process.stdout:
                    print(f"FFmpeg: {line.strip()}")
            except:
                pass
        
        threading.Thread(target=monitor_ffmpeg, daemon=True).start()
        
        time.sleep(2)
        if self.current_process.poll() is not None:
            print("配信プロセスが即座に終了")
            return False
        
        print("配信プロセス動作中")
        return True

    def stop_stream(self):
        if self.current_process:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            self.current_process = None

    def stream_qa_once(self, video_file):
        cmd = [
            'ffmpeg', '-i', video_file,
            '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv',
            self.rtmp_url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def question_monitor(self):
        last_modified = 0
        
        while self.streaming:
            try:
                if os.path.exists(self.question_file):
                    modified = os.path.getmtime(self.question_file)
                    if modified > last_modified:
                        with open(self.question_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        if content:
                            self.question_queue.put(content)
                            with open(self.question_file, 'w', encoding='utf-8') as f:
                                f.write("")
                        last_modified = modified
                
                time.sleep(1)
            except:
                time.sleep(1)

    def qa_processor(self):
        while self.streaming:
            try:
                question = self.question_queue.get(timeout=1)
                
                answer = ask_rag(question)
                qa_video = self.create_qa_video(question, answer)
                
                if qa_video:
                    self.stop_stream()
                    time.sleep(1)
                    self.stream_qa_once(qa_video)
                    time.sleep(1)
                    self.start_stream(self.loop_video)
                
            except queue.Empty:
                continue
            except:
                continue

def run_test():
    streamer = InteractiveStreamer()
    
    try:
        if not streamer.check_services():
            return
        
        if not streamer.start_rtmp_server():
            return
        
        time.sleep(3)
        
        # 待機画面作成（スレッド開始前に完了）
        waiting_script = {
            "scenes": [
                {
                    "text": "質問をお待ちしています。何でもお聞きください。",
                    "speaker_id": 1,
                    "background_color": "navy"
                },
                {
                    "text": "AIがあなたの質問にお答えします。お気軽にどうぞ。",
                    "speaker_id": 1,
                    "background_color": "darkgreen"
                }
            ]
        }
        
        print("待機画面作成中...")
        waiting_scenes = streamer.create_scenes_separately(waiting_script, "loop")
        if not waiting_scenes:
            print("待機画面作成失敗")
            return
        
        print("ループ動画作成中...")
        streamer.loop_video = streamer.create_loop_video_from_scenes(waiting_scenes)
        if not streamer.loop_video:
            print("ループ動画作成失敗")
            return
        
        # 質問ファイル初期化
        with open(streamer.question_file, 'w', encoding='utf-8') as f:
            f.write("")
        
        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        input("準備ができたらEnterを押してください...")
        
        # 配信開始（スレッド開始前）
        if not streamer.start_stream(streamer.loop_video):
            print("配信開始失敗")
            return
        
        print("配信開始完了")
        
        # スレッド開始
        question_thread = threading.Thread(target=streamer.question_monitor, daemon=True)
        qa_thread = threading.Thread(target=streamer.qa_processor, daemon=True)
        
        question_thread.start()
        qa_thread.start()
        
        print(f"質問は {streamer.question_file} に書き込んでください")
        
        while streamer.streaming:
            time.sleep(1)
    
    except KeyboardInterrupt:
        streamer.streaming = False
    finally:
        streamer.stop_stream()
        streamer.stop_rtmp_server()

if __name__ == "__main__":
    run_test()