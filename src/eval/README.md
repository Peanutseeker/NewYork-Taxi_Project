# 推荐策略评测

`evaluate.py` 接收一个策略文件，用二月订单模拟一辆出租车连续运行28天。

## 策略接口

策略文件必须实现：

```python
def recommend(
    current_datetime: datetime,
    current_location_id: int,
) -> list[int]:
    """Return three LocationIDs in ranked order."""
```

返回三个不重复的 `1..263` 区域编号，按推荐程度从高到低排列。

## 数据与时间

模拟器读取：

```text
data/raw/yellow_tripdata_2023-02.parquet
src/eval/travel_time_matrix.csv
```

二月订单按“日期、半小时 slot、上车区域”分组。只保留区域编号在 `1..263`、
上下车时间有效且载客时长不超过240分钟的订单；负数或无效收入按0处理。

一个 slot 为30分钟。矩阵移动时间和订单载客时间都按以下方式转换：

$$
\operatorname{Slots}(m)=\max\left(1,\left\lfloor\frac{m}{30}+0.5\right\rfloor\right)
$$

即四舍五入到最近的 slot，结果为0时按1个 slot 计算。矩阵中的 `inf` 表示不可达。

## 接单概率

设当前位置在当前 slot 中有 $n$ 条订单，则接单概率为：

$$
p(n)=\frac{n}{n+40}
$$

$p(0)=0$，并随订单数增加逐渐接近1。例如 $p(20)=1/3$、$p(40)=1/2$、
$p(100)\approx0.714$。

## 单次模拟

模拟从 `2023-02-01 00:00`、区域132开始，到 `2023-03-01 00:00` 结束：

1. 在当前“日期、slot、区域”统计订单数 $n$，以概率 $p(n)$ 判断是否接单。
2. 若接到订单，从该组真实订单中均匀抽取一条，获得其 `total_amount`，移动到
   `DOLocationID`，并按订单载客时长推进至少1个 slot。
3. 若未接到订单，调用 `recommend`，按 `60\%/30\%/10\%` 从 Top-1/2/3
   抽取目的地。不可达候选先删除，再按剩余权重抽取；全部不可达时留在当前区域。
4. 按时间矩阵中的移动时间推进至少1个 slot，到达后回到步骤1。

## 评测输出

`evaluate.py` 使用固定随机种子独立模拟200次，输出两个主要指标：

- `simulator_score`：200次模拟的平均日收入；
- `average_recommend_time_ms`：每次调用推荐函数并检查 Top-3 的平均耗时。

同时输出平均28天总收入、日收入标准差、接单数、移动次数和推荐调用次数。

## 固定参数

| 参数 | 固定值 |
| --- | --- |
| 开始时间 | `2023-02-01 00:00` |
| 结束时间 | `2023-03-01 00:00` |
| 模拟天数 | 28 |
| 司机初始区域 | 132 |
| slot | 30 分钟 |
| 模拟次数 | 200 |
| 基础随机种子 | `20230717` |

第 $r$ 次模拟使用随机种子 `20230717+r`，结果可复现。

## 运行

```bash
PYTHONPATH=src python3 -m eval.evaluate \
  --strategy src/2_recommendation_algorithm/baseline_1.py \
  --output tmp/baseline_1_evaluation.json
```

策略代码不得读取二月真实订单。该数据只能由评测器用于随机接单和收入计算。
