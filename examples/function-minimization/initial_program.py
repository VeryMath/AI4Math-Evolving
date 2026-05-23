# EVOLVE-BLOCK-START
"""调度函数优化：最小化平均延迟"""

import random


def scheduling_algorithm(num_tasks=50, num_resources=3):
    """
    简单调度算法，随机分配任务到资源

    Args:
        num_tasks: 任务数量
        num_resources: 可用资源数量

    Returns:
        平均延迟（单位：时间步）
    """
    # 每个任务的处理时间和截止时间
    tasks = []
    for i in range(num_tasks):
        processing_time = random.uniform(1, 10)
        deadline = random.uniform(20, 100)
        tasks.append(
            {"id": i, "processing_time": processing_time, "deadline": deadline}
        )

    # 随机调度：简单将任务分配到最早可用的资源
    resource_available_time = [0] * num_resources
    delays = []

    for task in tasks:
        # 选择最早可用的资源
        earliest_resource = min(
            range(num_resources), key=lambda r: resource_available_time[r]
        )
        start_time = resource_available_time[earliest_resource]
        finish_time = start_time + task["processing_time"]
        resource_available_time[earliest_resource] = finish_time

        # 计算延迟（如果任务在其截止时间之后完成）
        if finish_time > task["deadline"]:
            delay = finish_time - task["deadline"]
            delays.append(delay)

    # 返回平均延迟，如果没有延迟则返回0
    if delays:
        avg_delay = sum(delays) / len(delays)
    else:
        avg_delay = 0.0

    return avg_delay


# EVOLVE-BLOCK-END


def run_search():
    """
    入口函数，运行调度优化算法

    Returns:
        平均延迟值（越低越好）
    """
    avg_delay = scheduling_algorithm(num_tasks=50, num_resources=3)
    return avg_delay


if __name__ == "__main__":
    result = run_search()
    print(f"平均延迟: {result:.4f} 时间步")
