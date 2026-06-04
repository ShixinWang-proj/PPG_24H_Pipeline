from .router import MotionRouter
from .engine_a_time import EngineATimeDomain
from .engine_b_freq import EngineBFreqDomain
from .engine_c_fusion import FusionEngine

class PPG24hPipeline:
    def __init__(self, fs=100):
        self.fs = fs
        # 实例化各个模块 (相当于 C 里的结构体初始化)
        self.router = MotionRouter()
        self.engine_a = EngineATimeDomain(fs)
        self.engine_b = EngineBFreqDomain(fs)
        self.fusion = FusionEngine()
        
        self.global_tick = 0

    def process_sample(self, ppg_raw, acc_x, acc_y, acc_z, timestamp):
        """
        C语言风格接口：每次只塞入一个采样点
        """
        # 1. 路由层计算体动，更新状态
        motion_state, enmo = self.router.update(acc_x, acc_y, acc_z)
        
        raw_output = None
        
        # 2. 根据状态，决定谁来处理这个数据点
        if motion_state == "REST" or motion_state == "LIGHT_MOTION":
            # 静息态：走时域引擎（你现有的算法）
            # 顺便清空/挂起频域引擎的缓存，省电
            self.engine_b.reset() 
            raw_output = self.engine_a.process_point(ppg_raw, enmo, timestamp, self.global_tick)
            
        elif motion_state == "HEAVY_MOTION":
            # 剧烈运动态：走频域/自相关引擎
            # 时域引擎内部保持挂起，不再强行找波峰波谷
            self.engine_a.suspend() 
            raw_output = self.engine_b.process_point(ppg_raw, acc_x, acc_y, acc_z, timestamp)

        # 3. 融合层处理 (平滑突跳、填补短期间断)
        final_output = self.fusion.update(raw_output, motion_state, timestamp)
        
        self.global_tick += 1
        return final_output