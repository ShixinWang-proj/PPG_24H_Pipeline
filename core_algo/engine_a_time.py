import math

def c_style_median_of_5(arr):
    tmp = list(arr)
    for i in range(1, 5):
        key = tmp[i]
        j = i - 1
        while j >= 0 and tmp[j] > key:
            tmp[j + 1] = tmp[j]
            j -= 1
        tmp[j + 1] = key
    return tmp[2]

class EngineATimeDomain:
    def __init__(self, fs=100):
        self.fs = fs
        self.time_per_point_ms = 1000.0 / fs

        self.prev_clean_y = None
        self.MAX_SLEW_RATE = 8000.0

        self.med_buf = [0.0] * 5
        self.med_idx = 0
        self.med_filled = False

        self.MA_WINDOW = 12  # 或者 20
        self.ma_buf = [0.0] * self.MA_WINDOW
        self.ma_idx = 0
        self.ma_sum = 0.0
        self.ma_filled = False

        self.DC_ALPHA = 0.99
        self.prev_raw_dc = None
        self.prev_ac_y = 0.0

        # 注意：这里在测试中用无限增长的列表代替。
        # 等到翻译 C 语言时，必须改为长度为如 256 的环形数组 (Circular Buffer)
        self.ac_y_history = [] 

        self.PHASE_WAITING_FOR_VALLEY = 0
        self.PHASE_WAITING_FOR_PEAK = 1
        self.current_phase = self.PHASE_WAITING_FOR_VALLEY

        self.MIN_AC_AMP = 1000.0
        self.upper_th = 5000.0
        self.lower_th = -5000.0
        self.recent_p2p = 3000.0

        self.local_max = float('-inf')
        self.local_max_x = 0
        self.local_min = float('inf')
        self.local_min_x = 0

        self.v1_x = 0
        self.v1_y = 0.0
        self.precise_v1_x = 0.0

        self.backup_v1_x = 0
        self.backup_v1_y = 0.0
        self.backup_precise_v1_x = 0.0
        self.beat_just_added = False

        self.run_sum = 0.0
        self.run_enmo = 0.0
        self.run_pts = 0
        self.snap_area = 0.0
        self.snap_enmo = 0.0
        self.snap_pts = 0
        self.area_up_saved = 0.0

        self.baseline_rri = 0.0
        self.MIN_VALID_AMP = 15.0

        self.baseline_rri = 0.0
        self.MIN_VALID_AMP = 300.0
        self.FILTER_DELAY = 5.5  # 【新增】滤波器带来的相位延迟

    def suspend(self):
        """当发生剧烈运动被断开路由时，挂起并重置寻峰状态，防止串入脏数据"""
        self.current_phase = self.PHASE_WAITING_FOR_VALLEY
        self.run_sum = 0.0
        self.run_pts = 0
        self.run_enmo = 0.0
        self.beat_just_added = False

    def process_point(self, ppg_raw, enmo, timestamp, global_idx):
        """核心处理入口：每次仅吞吐 1 个样本"""
        # 1. 信号预处理
        ac_y = self.stage2_preprocessing(ppg_raw)
        
        # 2. 状态机流转与寻峰
        return self.stage3_state_machine(ac_y, enmo, global_idx, timestamp)

    def stage2_preprocessing(self, raw_y):
        self.med_buf[self.med_idx] = raw_y
        self.med_idx = (self.med_idx + 1) % 5
        if self.med_idx == 0: self.med_filled = True
        median_y = c_style_median_of_5(self.med_buf) if self.med_filled else raw_y

        if self.prev_clean_y is None: clamped_y = median_y
        else:
            diff = median_y - self.prev_clean_y
            if diff > self.MAX_SLEW_RATE: clamped_y = self.prev_clean_y + self.MAX_SLEW_RATE
            elif diff < -self.MAX_SLEW_RATE: clamped_y = self.prev_clean_y - self.MAX_SLEW_RATE
            else: clamped_y = median_y
        self.prev_clean_y = clamped_y

        self.ma_sum = self.ma_sum - self.ma_buf[self.ma_idx] + clamped_y
        self.ma_buf[self.ma_idx] = clamped_y
        self.ma_idx = (self.ma_idx + 1) % self.MA_WINDOW
        if self.ma_idx == 0: self.ma_filled = True

        if self.ma_filled: ma_y = self.ma_sum / self.MA_WINDOW
        else:
            current_count = self.ma_idx if self.ma_idx > 0 else self.MA_WINDOW
            ma_y = self.ma_sum / current_count if current_count > 0 else clamped_y

        if self.prev_raw_dc is None:
            self.prev_raw_dc = ma_y
            ac_y = 0.0
        else:
            ac_y = ma_y - self.prev_raw_dc + self.DC_ALPHA * self.prev_ac_y

        self.prev_raw_dc = ma_y
        self.prev_ac_y = ac_y
        self.ac_y_history.append(ac_y)
        return ac_y

    def stage3_state_machine(self, ac_y, enmo, current_global_i, time_str):
        # 【调试代码】监控真实数据的幅度水平和动态阈值
        # if current_global_i % 100 == 0:
        #     print(f"[{time_str}] AC_Y: {ac_y:.1f}, Envelope_P2P: {(self.upper_th - self.lower_th):.1f}, "
        #           f"Recent_P2P: {self.recent_p2p:.1f}, ENMO: {enmo:.1f}")
        if ac_y > self.upper_th: self.upper_th = ac_y
        if ac_y < self.lower_th: self.lower_th = ac_y

        self.upper_th -= (self.upper_th - ac_y) / 64.0
        self.lower_th += (ac_y - self.lower_th) / 64.0

        p2p_amp = self.upper_th - self.lower_th
        if p2p_amp < self.MIN_AC_AMP: p2p_amp = self.MIN_AC_AMP

        dynamic_prom = min(p2p_amp * 0.20, self.recent_p2p * 0.30)
        prominence_th = dynamic_prom
        MAX_PROMINENCE = 4000.0
        MIN_PROMINENCE = 400.0
        if prominence_th > MAX_PROMINENCE: prominence_th = MAX_PROMINENCE
        elif prominence_th < MIN_PROMINENCE: prominence_th = MIN_PROMINENCE

        output = None # 默认无心跳输出

        if self.current_phase == self.PHASE_WAITING_FOR_VALLEY:
            self.run_sum += ac_y
            self.run_enmo += enmo
            self.run_pts += 1

            if ac_y < self.local_min:
                self.local_min = ac_y
                self.local_min_x = current_global_i
                self.snap_area = self.run_sum
                self.snap_enmo = self.run_enmo
                self.snap_pts = self.run_pts
                
                # 超级回溯（吐出假点）逻辑。在单点流式中不方便从外部阵列pop()，
                # 但这里重置内部状态，防止错误延续。
                if self.beat_just_added:
                    depth_diff = self.v1_y - ac_y
                    time_diff_ms = (current_global_i - self.v1_x) * self.time_per_point_ms
                    if time_diff_ms < 1200.0 and depth_diff > (self.recent_p2p * 0.4):
                        self.beat_just_added = False
                        self.v1_x = self.backup_v1_x
                        self.v1_y = self.backup_v1_y
                        self.precise_v1_x = self.backup_precise_v1_x

            # 触发波谷 -> 提取心跳特征点
            if ac_y > (self.local_min + prominence_th):
                self.backup_v1_x = self.v1_x
                self.backup_v1_y = self.v1_y
                self.backup_precise_v1_x = self.precise_v1_x

                output = self.stage4_feature_extraction(time_str)
                self.beat_just_added = True if output is not None else False

                self.v1_x = self.local_min_x
                self.precise_v1_x = self.precise_v2_x
                self.v1_y = self.local_min

                over_run_sum = self.run_sum - self.snap_area
                over_run_pts = self.run_pts - self.snap_pts
                carried_area = over_run_sum - (over_run_pts * self.v1_y)

                self.run_sum = carried_area if carried_area > 0 else 0.0
                self.run_enmo = self.run_enmo - self.snap_enmo
                self.run_pts = over_run_pts

                self.current_phase = self.PHASE_WAITING_FOR_PEAK
                self.local_max = ac_y
                self.local_max_x = current_global_i

        elif self.current_phase == self.PHASE_WAITING_FOR_PEAK:
            current_height = ac_y - self.v1_y
            if current_height > 0: self.run_sum += current_height
            self.run_enmo += enmo
            self.run_pts += 1

            if ac_y > self.local_max:
                self.local_max = ac_y
                self.local_max_x = current_global_i
                self.snap_area = self.run_sum
                self.snap_enmo = self.run_enmo
                self.snap_pts = self.run_pts

            if ac_y < self.v1_y:
                if self.beat_just_added:
                    self.beat_just_added = False
                self.v1_x = self.backup_v1_x
                self.v1_y = self.backup_v1_y
                self.precise_v1_x = self.backup_precise_v1_x

                self.current_phase = self.PHASE_WAITING_FOR_VALLEY
                self.local_min = ac_y
                self.local_min_x = current_global_i
                self.snap_area = self.run_sum
                self.snap_pts = self.run_pts
                self.snap_enmo = self.run_enmo
                return None

            if ac_y < (self.local_max - prominence_th):
                self.area_up_saved = self.snap_area

                over_run_sum = self.run_sum - self.snap_area
                over_run_pts = self.run_pts - self.snap_pts
                self.run_sum = over_run_sum + (over_run_pts * self.v1_y)
                self.run_enmo = self.run_enmo - self.snap_enmo
                self.run_pts = over_run_pts

                self.current_phase = self.PHASE_WAITING_FOR_VALLEY
                self.local_min = ac_y
                self.local_min_x = current_global_i

        return output

    def stage4_feature_extraction(self, time_str):
        v2_x = self.local_min_x
        v2_y = self.local_min
        delta_x = 0.0
        
        # 抛物线插值，精确查找亚像素级别的谷底
        if 0 < v2_x < len(self.ac_y_history) - 1:
            y_m1 = self.ac_y_history[v2_x - 1]
            y_0 = self.ac_y_history[v2_x]
            y_p1 = self.ac_y_history[v2_x + 1]
            denom = y_m1 - 2 * y_0 + y_p1
            if denom != 0:
                delta_x = 0.5 * (y_m1 - y_p1) / denom
                delta_x = max(-1.0, min(1.0, delta_x))

        self.precise_v2_x = float(v2_x) + delta_x

        if self.precise_v1_x > 0.0:
            rri_ms = (self.precise_v2_x - self.precise_v1_x) * self.time_per_point_ms
            area_down = self.snap_area - (self.snap_pts * v2_y)

            if 350 <= rri_ms <= 2000 and area_down > 0:
                if self.baseline_rri == 0.0:
                    self.baseline_rri = rri_ms

                # 基础节律验证
                is_valid_beat = True
                if rri_ms > self.baseline_rri * 1.8: is_valid_beat = False
                elif rri_ms < self.baseline_rri * 0.45: is_valid_beat = False

                if is_valid_beat:
                    raw_hr = 60000.0 / rri_ms
                    self.baseline_rri = self.baseline_rri * 0.75 + rri_ms * 0.25
                    
                    amp_up = self.local_max - self.v1_y
                    amp_down = self.local_max - v2_y
                    beat_amp = max(amp_up, amp_down)
                    # 只有当这个波的振幅大于当前参考值的 30% 时，才承认它是有效生理波并更新阈值
                    if beat_amp > (self.recent_p2p * 0.3):
                        self.recent_p2p = self.recent_p2p * 0.9 + beat_amp * 0.1

                    raw_area_up = self.area_up_saved if amp_up > self.MIN_VALID_AMP else 0.0
                    raw_area_down = area_down if amp_down > self.MIN_VALID_AMP else 0.0

                    # 【修改】计算补偿后的实际波峰波谷位置
                    comp_peak_idx = max(0, int(round(self.local_max_x - self.FILTER_DELAY)))
                    comp_valley_idx = max(0, int(round(v2_x - self.FILTER_DELAY)))

                    return {
                        'timestamp': time_str,
                        'HR_Raw': round(raw_hr, 1),
                        'Area_Up': int(raw_area_up),
                        'Area_Down': int(raw_area_down),
                        'RRI_ms': round(rri_ms, 2),
                        'Peak_Index': comp_peak_idx,
                        'Valley_Index': comp_valley_idx,
                        'Filtered_Peak_Index': int(self.local_max_x),
                        'Filtered_Valley_Index': int(v2_x),
                        'Confidence': 90
                    }
                return None