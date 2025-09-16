"""まばたきアニメーション"""
import threading
import time
import random

class BlinkAnimator:
    def __init__(self, expression_state):
        self.expression_state = expression_state
        self._stop_event = threading.Event()
        self._thread = None
    
    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def _blink_loop(self):
        while not self._stop_event.is_set():
            if not self.expression_state.is_talking:
                original_eyes = self.expression_state.current_eyes
                self.expression_state.set_eyes("UU")
                time.sleep(0.12)  # まばたき時間
                self.expression_state.set_eyes(original_eyes)
                time.sleep(2.0 + random.random() * 3.0)
            else:
                time.sleep(0.1)
