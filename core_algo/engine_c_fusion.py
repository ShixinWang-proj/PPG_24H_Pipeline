class FusionEngine:
    def __init__(self):
        # 1D 卡尔曼滤波器内部状态
        self.x = 75.0  # 状态量 x：当前估计的真实心率 (初始化为 75)
        self.p = 100.0  # 误差协方差 P：表示对当前估计的不确定度
        self.q = 1.0  # 过程噪声 Q：人体心率通常不会在一秒内突变，设为较小值

    def update(self, raw_output, motion_state, timestamp):
        # 如果上游两个引擎都没攒够数据输出，直接返回
        if raw_output is None:
            return None

        z = raw_output.get('HR_Raw')
        if z is None or z <= 0:
            return raw_output

        # 提取置信度，用来动态决定测量噪声 R
        # 置信度越高(例如 90)，R 越小，越相信 z；置信度越低(例如 50)，R 越大，越相信之前的预测
        conf = raw_output.get('Confidence', 50)
        r = max(5.0, 100.0 - conf)

        # --- 1. 预测阶段 (Prediction) ---
        # 假设人体心率状态转移方程为 x(k) = x(k-1)
        # self.x 保持不变
        self.p = self.p + self.q

        # --- 2. 更新阶段 (Update) ---
        # 计算卡尔曼增益 K
        k = self.p / (self.p + r)

        # 利用当前观测值 z 修正当前估计
        self.x = self.x + k * (z - self.x)

        # 更新误差协方差
        self.p = (1.0 - k) * self.p

        # --- 3. 输出重写 ---
        # 我们保留原始心率方便对比，新增 HR_Filtered 作为最终结果
        raw_output['HR_Filtered'] = round(self.x, 1)

        return raw_output