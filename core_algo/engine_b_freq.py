import numpy as np


class EngineBFreqDomain:
    def __init__(self, fs=100):
        self.fs = fs
        self.WINDOW_SIZE = 512
        self.ppg_buf = [0.0] * self.WINDOW_SIZE
        self.acc_buf = [0.0] * self.WINDOW_SIZE
        self.buf_idx = 0
        self.is_filled = False

    def reset(self):
        self.buf_idx = 0
        self.is_filled = False

    def process_point(self, ppg_raw, acc_x, acc_y, acc_z, timestamp):
        self.ppg_buf[self.buf_idx] = ppg_raw
        # 提取动态加速度的近似模值（减去 1g 重力基准，这里简化为求合矢去均值）
        acc_norm = (acc_x ** 2 + acc_y ** 2 + acc_z ** 2) ** 0.5
        self.acc_buf[self.buf_idx] = acc_norm

        self.buf_idx += 1

        if self.buf_idx >= self.WINDOW_SIZE:
            self.is_filled = True

            # 1. 转换为 numpy 数组并去除直流分量 (DC removal)
            ppg_arr = np.array(self.ppg_buf)
            acc_arr = np.array(self.acc_buf)
            ppg_arr -= np.mean(ppg_arr)
            acc_arr -= np.mean(acc_arr)

            # 2. 加汉明窗 (Hamming Window)，减少频谱泄漏
            window = np.hamming(self.WINDOW_SIZE)
            ppg_windowed = ppg_arr * window
            acc_windowed = acc_arr * window

            # 3. FFT 计算 (模拟 C 语言 CMSIS-DSP 的 rfft)
            freqs = np.fft.rfftfreq(self.WINDOW_SIZE, 1.0 / self.fs)
            ppg_fft = np.abs(np.fft.rfft(ppg_windowed))
            acc_fft = np.abs(np.fft.rfft(acc_windowed))

            # 限制心率和步频的合理搜索范围：0.8Hz 到 3.5Hz (即 48 到 210 BPM)
            valid_idx = np.where((freqs >= 0.8) & (freqs <= 3.5))[0]

            if len(valid_idx) > 0:
                # 4. 找 ACC 频谱中的最高峰 -> 当前主要运动步频
                acc_peak_idx = valid_idx[np.argmax(acc_fft[valid_idx])]
                acc_peak_freq = freqs[acc_peak_idx]

                # 5. 在 PPG 频谱中，将步频及其一阶谐波的频点置零（带宽设为 ±0.2 Hz）
                mask_width = 0.2
                for i in valid_idx:
                    f = freqs[i]
                    if abs(f - acc_peak_freq) < mask_width or abs(f - 2 * acc_peak_freq) < mask_width:
                        ppg_fft[i] = 0.0

                # 6. 在“净化”后的 PPG 频谱中找剩余的最高峰 -> 运动心率
                hr_peak_idx = valid_idx[np.argmax(ppg_fft[valid_idx])]
                hr_peak_freq = freqs[hr_peak_idx]
                estimated_hr = hr_peak_freq * 60.0
            else:
                estimated_hr = 140.0  # 数据异常时的兜底值

            # 7. 数据搬运，留存重叠部分 (Overlap = 384)
            shift_len = 128
            self.ppg_buf[:self.WINDOW_SIZE - shift_len] = self.ppg_buf[shift_len:]
            self.acc_buf[:self.WINDOW_SIZE - shift_len] = self.acc_buf[shift_len:]
            self.buf_idx = self.WINDOW_SIZE - shift_len

            return {
                'timestamp': timestamp,
                'HR_Raw': round(estimated_hr, 1),
                'Area_Up': 0,
                'Area_Down': 0,
                'Confidence': 50  # 频域的置信度统一设为 50，交由融合层判断
            }

        return None