import os
import time
import pandas as pd
import numpy as np
from pc_tools.dataloader import PPGDataLoader
from core_algo.main_pipeline import PPG24hPipeline


def main():
    base_path = r'D:\Workspace\5_Data\bupt_ring_selftest\wsx\报告\0526-1109-0527-1032'
    csv_file = os.path.join(base_path, 'wang戒指_merged.csv')

    if not os.path.exists(csv_file):
        print(f"❌ 找不到真实数据，请检查路径: {csv_file}")
        return

    print(f"正在加载数据: {csv_file}")
    df = pd.read_csv(csv_file)

    # 截取前 10 分钟测试 (100Hz = 60000 点)
    TEST_POINTS = 60000
    if len(df) > TEST_POINTS:
        df = df.head(TEST_POINTS)

    loader = PPGDataLoader(df)
    pipeline = PPG24hPipeline(fs=100)

    continuous_records = []
    event_records = []
    start_time = time.time()

    # 模拟 C 语言流水线运行
    for timestamp, ppg_raw, acc_x, acc_y, acc_z in loader.stream_data():
        output = pipeline.process_sample(ppg_raw, acc_x, acc_y, acc_z, timestamp)

        # 1. 保存用于画图的【连续波形】字典
        # 使用你 Jupyter 脚本里需要的列名：ied, motion, ac_y
        continuous_records.append({
            'ied': ppg_raw,
            'motion': pipeline.router.enmo_buffer[pipeline.router.buf_idx - 1] if pipeline.router.enmo_buffer else 0,
            'ac_y': pipeline.engine_a.prev_ac_y
        })

        # 2. 保存【心跳打点】事件
        if output is not None:
            event_records.append(output)

    cost_time = time.time() - start_time

    # 将记录导出为 CSV，供 Jupyter 读取
    os.makedirs("data", exist_ok=True)
    pd.DataFrame(continuous_records).to_csv("data/pipeline_continuous.csv", index=False)
    pd.DataFrame(event_records).to_csv("data/pipeline_events.csv", index=False)

    print(f"\n--- ✅ 仿真结束 ---")
    print(f"总点数: {len(continuous_records)} | 输出特征: {len(event_records)} 次 | 耗时: {cost_time:.3f} 秒")
    print("现在你可以去 Jupyter Notebook 运行你的可视化交互代码了！")


if __name__ == "__main__":
    main()
