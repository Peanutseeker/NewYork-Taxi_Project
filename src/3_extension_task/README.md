# Part 3：多步规划

扩展策略共用 `planning_core.py`，只读取训练集生成的区域统计和时间矩阵。

| 文件 | 方法 |
| --- | --- |
| `random_strategy.py` | 固定随机种子的随机策略下界 |
| `expected_income.py` | 按预计接单收入除以移动 slot 数排序 |
| `dynamic_programming.py` | 两步 Bellman 动态规划 |
| `beam_search.py` | 四步规划，每个后续状态保留 8 个动作 |
| `hybrid_dynamic_programming.py` | Baseline 2 主分数加三步未来价值 |
| `two_step_income_rate.py` | 两次尝试的期望收入率规划 |

运行方式：

```bash
PYTHONPATH=src python -m eval.evaluate \
  --strategy src/3_extension_task/dynamic_programming.py \
  --output tmp/dynamic_programming_evaluation.json
```

所有策略均实现：

```python
recommend(current_datetime, current_location_id) -> list[int]
```

## 评测结果

模拟器 v5 使用30分钟 slot。下表是每种策略顺序运行200轮的结果：

| 方法 | 单次推荐/ms | 平均28天总收入 | 日均收入 | 日均标准差 | 评测总耗时/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 两步收入率 | 0.339 | **18389.32** | **656.76** | 101.66 | 61.02 |
| 预计收入率 | **0.036** | 17828.30 | 636.72 | 104.63 | 20.36 |
| 两步动态规划 | 0.628 | 16779.47 | 599.27 | 91.58 | 106.85 |
| 混合动态规划 | 0.325 | 15203.29 | 542.97 | 90.63 | 59.35 |
| 四步 Beam Search | 0.633 | 14950.34 | 533.94 | 116.81 | 114.61 |
| Baseline 2 | 0.092 | 14739.06 | 526.40 | 104.07 | 27.35 |
| Baseline 1 | 0.054 | 13618.29 | 486.37 | 48.45 | 21.36 |
| 随机策略 | 0.004 | 171.44 | 6.12 | 5.74 | 16.21 |

两步收入率策略的日均收入比 Baseline 2 高约24.77%。
