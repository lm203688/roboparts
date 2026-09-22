# 数据许可（DATA-LICENSE）— RoboParts

> RoboParts 采用**双轨许可**：本仓库的**代码**见 [`LICENSE`](./LICENSE)（MIT），
> **数据**适用本文件（CC BY 4.0）。
>
> 【为什么拆成两个文件】此前这两条写在同一个 `LICENSE` 里，GitHub 的许可识别器
> 读不懂自定义混排文本，仓库页 `license` 字段长期显示 **`NOASSERTION`** ——
> 一个以"开源数据层"自我定位的项目，在自己的 GitHub 页上显示不出任何许可，
> 直接影响开源圈的信任与收录。故 `LICENSE` 只放**逐字 MIT 全文**（可被识别），
> 数据那条挪到本文件。

## 适用范围

`api/` 下的全部 JSON 数据集（含 `entities.json`、`mechanical_interfaces.json`、
各品类文件）、`roboparts-dataset-github/` 分发目录，以及经
<https://roboparts.cc/api/> 提供的同源数据。

## 许可

Creative Commons Attribution 4.0 International (CC BY 4.0)

- 全文：<https://creativecommons.org/licenses/by/4.0/legalcode>
- 摘要：<https://creativecommons.org/licenses/by/4.0/>

你可以自由使用、修改、再分发与商用，条件是注明来源。建议署名格式：

```
数据来源：RoboParts (https://roboparts.cc)，CC BY 4.0
```

本条与 `roboparts-dataset-github/LICENSE` 以及 API 响应中
`meta.access.license` 声明的许可一致。

## 数据使用须知（不是许可条款，是诚实提示）

引用本库数据前请知悉以下事实，它们同样公开写在 API 响应的 `meta` 里：

1. 本库参数为**厂商公开声明值，未经我方实测复现**。请勿当作实测数据使用。
2. 跨厂商可直接横向比较的 A 级条目为 **0 条**。
3. 「两个零件能否装到一起」这个问题，本库目前多数情况答不了 ——
   机械接口有线索的实体占 **5.69%**（declared 15 + partial 10 / 435 适用，
   截至 2026-09-15，历史快照）。**该百分比禁止在文案里手写**，
   对外一律以 `api/entities.json` → `meta.mechanical_interface_coverage.fill_pct`
   与 <https://roboparts.cc/api/entities.json> 的现算值为准；
   查不到的实体标注为 `not_declared`，而非留空或猜测。
4. 每条数据带 `source_tier`（A/B/C）与 `confidence`，请据此判断可信度。
   Tier C 为无溯源历史导入，confidence 上限 0.30。
5. `api/mechanical_interfaces.json` 中标注 `authority` 为 `"roboparts_internal"`
   的键名（如 `mount_type_enum.roboparts_extension` 下的取值）**不是任何标准的
   术语**，是本平台内部建模口径，请勿当作标准编码向下游转述。

本平台不生产、不代理任何零部件，与所收录厂商无销售利益关系。
