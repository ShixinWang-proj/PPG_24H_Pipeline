import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_pipeline_results():
    data_path = os.path.join("data", "pipeline_output.csv")
    events_path = os.path.join("data", "pipeline_events.csv")
    
    if not os.path.exists(data_path) or not os.path.exists(events_path):
        print("❌ 找不到结果数据，请先运行 run_simulation.py")
        return

    # 读取数据
    df = pd.read_csv(data_path)
    events = pd.read_csv(events_path)
    
    # 转换 Timestamp 为序号，方便横坐标对齐
    df['idx'] = range(len(df))
    # 尝试将 events 里的 timestamp 映射回 idx
    event_idx_map = dict(zip(df['Timestamp'], df['idx']))
    events['idx'] = events['timestamp'].map(event_idx_map)

    # 创建 3 个纵向排列的子图
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    fig.suptitle('PPG 24H Hybrid Pipeline - Internal State Visualizer', fontsize=16)

    # --- 子图 1: 路由状态与加速度能量 ---
    ax0 = axes[0]
    ax0.plot(df['idx'], df['Acc_Norm'], label='ACC ENMO (Motion Energy)', color='gray', alpha=0.7)
    
    # 填充高亮运动区域
    ax0.fill_between(df['idx'], 0, df['Acc_Norm'].max(), 
                     where=(df['Motion_State'] == 1), 
                     color='red', alpha=0.2, label='HEAVY_MOTION Active')
    
    ax0.set_title("Router Stage: Motion Energy & Engine Switching")
    ax0.set_ylabel("ENMO")
    ax0.legend(loc="upper right")
    ax0.grid(True, linestyle='--', alpha=0.6)

    # --- 子图 2: Engine A 的内部状态与包络线 ---
    ax1 = axes[1]
    ax1.plot(df['idx'], df['AC_Y'], label='Engine A: AC Signal', color='black', linewidth=1.2)
    
    # 画动态阈值的上下限包络
    ax1.plot(df['idx'], df['Upper_Th'], label='Upper Envelope', color='green', linestyle='--', alpha=0.7)
    ax1.plot(df['idx'], df['Lower_Th'], label='Lower Envelope', color='blue', linestyle='--', alpha=0.7)
    
    ax1.set_title("Engine A (Time Domain): Adaptive Thresholds & AC Signal")
    ax1.set_ylabel("Amplitude")
    ax1.legend(loc="upper right")
    ax1.grid(True, linestyle='--', alpha=0.6)
    # 限制 Y 轴显示范围，防止运动时的极值把图撑破
    ax1.set_ylim(-3000, 3000)

    # --- 子图 3: 最终心率输出与打点 ---
    ax2 = axes[2]
    # 把心跳打点标在一条横线上
    ax2.scatter(events['idx'], [1] * len(events), color='magenta', marker='v', s=100, label='Heartbeat Detected (Event)')
    
    # 标注心率数值
    for _, row in events.iterrows():
        if pd.notna(row['idx']):
            ax2.text(row['idx'], 1.1, f"{row['HR_Raw']:.0f}", rotation=45, fontsize=8, ha='left')

    ax2.set_title("Pipeline Output: Heart Rate & Detection Events")
    ax2.set_ylabel("Heartbeat")
    ax2.set_yticks([]) # 隐藏 Y 轴刻度
    ax2.legend(loc="lower right")
    ax2.set_xlabel("Sample Index")
    ax2.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_pipeline_results()