import math

class MotionRouter:
    def __init__(self):
        self.baseline_1g = 0.0
        self.enmo_buffer = [0.0] * 100 
        self.buf_idx = 0

        self.MOTION_TH = 400.0
        self.current_state = "REST" 

    def update(self, acc_x, acc_y, acc_z):
        acc_norm = math.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
        if self.baseline_1g == 0.0:
             self.baseline_1g = acc_norm
             
        enmo = abs(acc_norm - self.baseline_1g)
        
        if enmo < 300.0: 
            self.baseline_1g = self.baseline_1g * 0.99 + acc_norm * 0.01
            
        self.enmo_buffer[self.buf_idx] = enmo
        self.buf_idx = (self.buf_idx + 1) % len(self.enmo_buffer)
        avg_enmo = sum(self.enmo_buffer) / len(self.enmo_buffer)
        
        if avg_enmo > self.MOTION_TH:
            self.current_state = "HEAVY_MOTION"
        elif avg_enmo < (self.MOTION_TH * 0.5):
            self.current_state = "REST"
            
        return self.current_state, enmo