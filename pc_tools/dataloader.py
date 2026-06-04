import pandas as pd
import numpy as np


class PPGDataLoader:
    def __init__(self, df):
        """直接接收外部传入的 DataFrame"""
        self.data = df.copy()

        # 你的预处理逻辑：反相红外信号 (ied)
        if 'ied' in self.data.columns:
            self.data['ied'] = -1.0 * self.data['ied']

    def stream_data(self):
        """模拟硬件中断，逐个样本点吐出数据"""
        for row in self.data.itertuples():
            # 将 Date 和 Time 拼接成字符串时间戳
            date_str = getattr(row, 'Date', '')
            time_str = getattr(row, 'Time', '')
            timestamp = f"{date_str} {time_str}".strip()

            if not timestamp:
                timestamp = str(row.Index)

            ppg_raw = float(row.ied)
            acc_x = float(row.accX)
            acc_y = float(row.accY)
            acc_z = float(row.accZ)

            yield timestamp, ppg_raw, acc_x, acc_y, acc_z