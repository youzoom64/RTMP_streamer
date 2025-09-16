"""Node.js RTMPサーバー制御"""
import subprocess
import socket
import time

def trace_log(message, level="INFO"):
    import time, threading
    timestamp = time.time()
    thread_id = threading.current_thread().ident
    print(f"[{timestamp:.3f}][{thread_id}][{level}] {message}")

class RTMPServer:
    def __init__(self):
        self.process = None
        self.rtmp_url = "rtmp://localhost:1935/live/test-stream"
    
    def start(self) -> bool:
        trace_log("RTMPサーバー起動開始")
        try:
            trace_log("Node.jsプロセス起動中...")
            self.process = subprocess.Popen(
                ['node', 'rtmp_server.js'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            trace_log(f"Node.jsプロセスID: {self.process.pid}")
            
            trace_log("サーバー起動待機開始(3秒)")
            time.sleep(3)
            trace_log("サーバー起動待機完了")
            
            trace_log("接続確認開始")
            if self._check_connection():
                trace_log("RTMPサーバー起動成功")
                return True
            else:
                trace_log("RTMPサーバー接続確認失敗", "ERROR")
                self.stop()
                return False
                
        except FileNotFoundError:
            trace_log("Node.js未発見", "ERROR")
            return False
        except Exception as e:
            trace_log(f"RTMPサーバー起動例外: {e}", "ERROR")
            return False
    
    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            trace_log("RTMPサーバー停止")
    
    def _check_connection(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('localhost', 1935))
        sock.close()
        return result == 0