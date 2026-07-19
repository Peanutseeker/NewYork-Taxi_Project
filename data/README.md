# New York Taxi 项目

本目录包含课程提供的原始数据、区域信息和未清洗的数据划分。训练集与验证集
保留原始订单字段，数据清洗由学生完成。

## 目录与用途

| 路径 | 用途 |
| --- | --- |
| `data/raw/yellow_tripdata_2023-01.parquet` | 2023年1月 Yellow Taxi 原始订单。 |
| `data/raw/yellow_tripdata_2023-02.parquet` | 2023年2月 Yellow Taxi 原始订单，仅供评测器使用。 |
| `data/meta/taxi_zone_lookup.csv` | 区域编号、行政区和区域名称对照表。 |
| `data/meta/taxi_zones.zip` | Taxi Zone 地理边界 Shapefile 文件包，可用于地图可视化。 |
| `data/processed/train_uncleaned.parquet` | 以 `tpep_dropoff_datetime` 切分的 1 月 1 日至 24 日订单；未清洗。 |
| `data/processed/validation_uncleaned.parquet` | 以 `tpep_dropoff_datetime` 切分的 1 月 25 日至 31 日订单；未清洗。 |

## 表头示例

### 原始订单、训练集与验证集

`data/raw/yellow_tripdata_2023-01.parquet`、`data/processed/train_uncleaned.parquet` 和 `data/processed/validation_uncleaned.parquet` 的表头如下：

```text
VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, passenger_count,
trip_distance, RatecodeID, store_and_fwd_flag, PULocationID, DOLocationID,
payment_type, fare_amount, extra, mta_tax, tip_amount, tolls_amount,
improvement_surcharge, total_amount, congestion_surcharge, airport_fee
```

`data/raw/yellow_tripdata_2023-02.parquet` 的其余字段相同；最后一列在源文件中写作 `Airport_fee`（首字母大写）。

- `PULocationID` / `DOLocationID`：上车 / 下车区域编号；可与区域对照表连接。
- `tpep_pickup_datetime` / `tpep_dropoff_datetime`：上车 / 下车时间。
- `fare_amount`、`tip_amount`、`total_amount`：订单收益相关字段。

### 区域编号对照表

`data/meta/taxi_zone_lookup.csv`：

```text
LocationID, Borough, Zone, service_zone
```

## 数据来源

原始行程记录来自 [NYC Taxi & Limousine Commission Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)。
