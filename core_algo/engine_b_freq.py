class EngineBFreqDomain:
    def __init__(self, fs=100):
        self.fs = fs
        self.WINDOW_SIZE = 512 # 5秒数据，刚好凑够 2^9，方便单片机做 FFT
        self.ppg_buf = [0.0] * self.WINDOW_SIZE
        self.acc_buf = [0.0] * self.WINDOW_SIZE
        self.buf_idx = 0
        self.is_filled = False

    def reset(self):
        self.buf_idx = 0
        self.is_filled = False

    def process_point(self, ppg_raw, acc_x, acc_y, acc_z, timestamp):
        # 存入环形缓冲区
        self.ppg_buf[self.buf_idx] = ppg_raw
        self.acc_buf[self.buf_idx] = acc_x # 简化：拿运动方向最剧烈的轴
        
        self.buf_idx += 1
        
        # 每隔一定步长 (例如 128 个点，即 1.28 秒) 输出一次心率
        if self.buf_idx >= self.WINDOW_SIZE:
            self.is_filled = True
            
            # --- 以下逻辑未来在 C 语言中调用 CMSIS-DSP 库实现 ---
            # 1. 对 ppg_buf 做 FFT 得到 PPG_频谱
            # 2. 对 acc_buf 做 FFT 得到 ACC_频谱
            # 3. 寻找 ACC_频谱的最高峰 -> 步频
            # 4. 在 PPG_频谱 中，将步频对应的频点置零（抹除步频能量）
            # 5. 在 PPG_频谱 中寻找剩余的最高峰 -> 运动心率
            
            estimated_hr = 140.0 # 模拟计算结果
            
            # 数据搬运，留存重叠部分 (Overlap = 384)
            shift_len = 128
            for i in range(self.WINDOW_SIZE - shift_len):
                self.ppg_buf[i] = self.ppg_buf[i + shift_len]
                self.acc_buf[i] = self.acc_buf[i + shift_len]
            self.buf_idx = self.WINDOW_SIZE - shift_len
            
            return {
                'timestamp': timestamp,
                'HR_Raw': estimated_hr,
                'Area_Up': 0,    # 运动态，放弃面积提取！置 0 或标为无效
                'Area_Down': 0,
                'Confidence': 50 # 频域的置信度通常设为中等
            }
            
        return None # 缓存未满或未到步长，暂无新输出