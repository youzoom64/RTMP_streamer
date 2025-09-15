# test_script.py (改善版)
import os
import time
import threading
import queue
from streamer import VoiceVoxStreamer

class InteractiveStreamer(VoiceVoxStreamer):
    def __init__(self):
        super().__init__()
        self.question_queue = queue.Queue()
        self.streaming = False
        self.current_process = None
        self.loop_video = None
        
    # [既存のメソッドは同じ]
    
    def question_handler(self):
        """ファイル監視による質問受付"""
        question_file = "questions.txt"
        last_modified = 0
        
        print(f"質問は {question_file} に書き込んでください")
        
        while self.streaming:
            try:
                if os.path.exists(question_file):
                    modified = os.path.getmtime(question_file)
                    if modified > last_modified:
                        with open(question_file, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        if content:
                            self.question_queue.put(content)
                            print(f"質問受付: {content}")
                            # ファイルをクリア
                            with open(question_file, 'w') as f:
                                f.write("")
                        last_modified = modified
                
                time.sleep(1)
            except Exception as e:
                print(f"質問受付エラー: {e}")
                time.sleep(1)

def run_test():
    print("=== インタラクティブ配信テスト ===")
    print("質問は questions.txt ファイルに書き込んでください")
    
    # questions.txtを作成
    with open("questions.txt", "w", encoding="utf-8") as f:
        f.write("")
    
    # [既存のrun_test処理]

if __name__ == "__main__":
    run_test()