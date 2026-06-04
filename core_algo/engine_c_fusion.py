class FusionEngine:
    def update(self, raw_output, motion_state, timestamp):
        # 未来这里放卡尔曼滤波，目前直接透传
        return raw_output