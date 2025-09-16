"""表情状態管理"""
import threading

class ExpressionState:
    def __init__(self):
        self.current_mouth = "むふ"
        self.current_eyes = "普通目"
        self.is_talking = False
        self._lock = threading.Lock()
    
    def set_mouth(self, mouth: str):
        with self._lock:
            self.current_mouth = mouth
    
    def set_eyes(self, eyes: str):
        with self._lock:
            self.current_eyes = eyes
    
    def set_talking(self, talking: bool):
        with self._lock:
            self.is_talking = talking
    
    def get_current_expression(self) -> tuple:
        with self._lock:
            return self.current_mouth, self.current_eyes
