"""
评估器：调度函数优化 - 最小化平均延迟
"""

import importlib.util
import random
import time
import concurrent.futures
import traceback
import signal
from openevolve.evaluation_result import EvaluationResult


def run_with_timeout(func, args=(), kwargs={}, timeout_seconds=10):
    """
    使用线程池在超时限制内运行函数

    Args:
        func: 要运行的函数
        args: 位置参数
        kwargs: 关键字参数
        timeout_seconds: 超时秒数

    Returns:
        函数结果或抛出TimeoutError
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout_seconds)
            return result
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"函数在 {timeout_seconds} 秒后超时")


def safe_float(value):
    """安全地将值转换为float"""
    try:
        return float(value)
    except (TypeError, ValueError):
        print(f"警告：无法将值 {value} (类型 {type(value)}) 转换为 float")
        return None


def evaluate(program_path):
    """
    评估调度优化程序

    Args:
        program_path: 程序文件路径

    Returns:
        EvaluationResult，包含各种指标
    """
    num_trials = 10
    scores = []
    delays = []
    execution_times = []
    success_count = 0

    for trial in range(num_trials):
        try:
            start_time = time.time()

            # 加载程序
            spec = importlib.util.spec_from_file_location("program", program_path)
            program = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(program)

            # 检查必要函数
            if not hasattr(program, "run_search"):
                print(f"试用 {trial}：程序缺少 'run_search' 函数")
                continue

            # 运行优化算法
            result = run_with_timeout(program.run_search, timeout_seconds=10)
            end_time = time.time()

            # 处理结果
            avg_delay = safe_float(result)
            if avg_delay is None:
                print(f"试用 {trial}：无法解析结果 {result}")
                continue

            # 检查是否有效
            if avg_delay < 0:
                print(f"试用 {trial}：延迟不能为负数: {avg_delay}")
                continue

            delays.append(avg_delay)
            execution_times.append(end_time - start_time)
            success_count += 1

            # 延迟越低越好，转换为分数
            # 使用指数衰减：延迟越低，分数越高
            score = 1.0 / (1.0 + avg_delay / 10.0)
            scores.append(score)

        except TimeoutError as e:
            print(f"试用 {trial}：超时 - {str(e)}")
            continue
        except Exception as e:
            print(f"试用 {trial}：错误 - {str(e)}")
            continue

    # 所有试用都失败
    if success_count == 0:
        error_artifacts = {
            "error_type": "AllTrialsFailed",
            "error_message": f"全部 {num_trials} 个试用失败",
            "suggestion": "检查程序是否有无限循环，确保 run_search() 返回有效数值",
        }
        return EvaluationResult(
            metrics={
                "avg_delay": float("inf"),
                "reliability_score": 0.0,
                "combined_score": 0.0,
                "error": "所有试用失败",
            },
            artifacts=error_artifacts,
        )

    # 计算指标
    avg_delay_score = float(sum(delays) / len(delays))
    reliability_score = float(success_count / num_trials)

    # 使用平均延迟计算分数（延迟越低越好）
    # 延迟为0时得满分，延迟增加时分数下降
    if avg_delay_score == 0:
        delay_score = 1.0
    else:
        delay_score = 1.0 / (1.0 + avg_delay_score / 20.0)

    # 综合分数：结合延迟分数和可靠性
    combined_score = 0.8 * delay_score + 0.2 * reliability_score

    artifacts = {
        "avg_delay": f"{avg_delay_score:.4f}",
        "success_rate": f"{reliability_score:.2%}",
        "avg_execution_time": f"{sum(execution_times) / len(execution_times):.4f}s",
    }

    return EvaluationResult(
        metrics={
            "avg_delay": avg_delay_score,
            "delay_score": delay_score,
            "reliability_score": reliability_score,
            "combined_score": combined_score,
        },
        artifacts=artifacts,
    )


if __name__ == "__main__":
    # 测试评估器
    import sys

    if len(sys.argv) > 1:
        result = evaluate(sys.argv[1])
        print(f"评估结果: combined_score = {result.metrics['combined_score']:.4f}")
    else:
        print("用法: python evaluator.py <program_path>")
