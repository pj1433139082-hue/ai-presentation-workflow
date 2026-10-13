# 逐页来源与示例边界

## 样稿定位

本文件对应 `deck-草稿.pptx`，为本地展示草稿。它展示研究方案表达方式，不代表实际试验、正式科研结论、经人类批准的生产演示或完整 human G1–G5 流程认证。所有操作参数均留给真实项目按原水、药剂、仪器和本地 SOP 确认。

## 外部方法背景

| 来源 | 用途 | 边界 |
|---|---|---|
| [Ireland EPA, Water Treatment Manual: Coagulation, Flocculation & Clarification (2002)](https://www.epa.ie/publications/compliance--enforcement/drinking-water/advice--guidance/EPA_water_treatment_mgt_coag_flocc_clar2.pdf) | 支持烧杯试验作为比较混凝条件、观察沉后水指标的概念背景。 | 该手册不是本样稿对应水源或设备的已批准操作规程；样稿不把其数值参数移植为通用建议。 |
| [California State Water Resources Control Board, Jar Testing Made Easy (2020)](https://www.waterboards.ca.gov/drinking_water/programs/districts/docs/mendocino/jar_testing_made_easy_aug7_2020.pdf) | 支持 jar test 条件比较及有序记录的背景说明。 | 指南中的程序属于其具体背景；本稿不据此宣称所有水样/装置都应照搬同一程序。 |

不引用 ASTM 内容或标准文本。本样稿无实验结果、无真实商业/研究数据、无临床或运行效果声明。

## 逐页映射

| 页 | 内容 / 可核对表述 | 来源或数据类型 | 可支持的范围 |
|---|---|---|---|
| 1 | “烧杯试验设计草案”；标注“方案演示 · 不代表已开展实验”。 | 本地样稿的任务范围；生成的透明烧杯 PNG。 | 定义本展示物的性质，不作外部事实主张。 |
| 2 | 把混凝剂剂量（可选 pH）作为比较因素，沉后浊度作为观测示例；要求原水批次、操作规程和读数条件保持可比。 | EPA (2002) 与 California SWRCB (2020) 的方法背景；具体参数未设定。 | 仅支持方案结构示意。具体因素水平、仪器和程序须本地确定。 |
| 3 | D1–D5 × P1–P3 的条件矩阵、空白/零剂量对照占位和随机顺序提醒。 | 编码和矩阵为本地编造的设计版式，不是来源文件的实验参数。 | 只演示如何组织因素组合；不建议具体水平或重复数。 |
| 4 | 取样/编码、配液/加药、混合/沉降、测量/记录的顺序示意；提示本地程序和偏差记录。 | 方法方案的通用表达；EPA / SWRCB 只作概念背景；透明絮体 PNG 为生成插图。 | 不构成可执行 SOP；本地安全规程和设备方法优先。 |
| 5 | D1–D5 示例值 16、11、8、9、12 NTU 的柱形图。 | `data-demo.csv` 中明确标记的编造示意数据。 | 只演示原生图表布局。不可解释为实测、因果关系、性能证明或推荐剂量。 |

## 数据、图像和构建

- `data-demo.csv` 每行均标注“虚构示意数据；非实测；仅用于图表版式”。数据由样稿作者编造，不来自论文、数据库或实际测量。
- `assets/jar-test-beaker.png` 与 `assets/floc-cluster.png` 是用内置图像生成工具生成的透明 PNG 单体插图，不是科研照片、实验记录或原水样本。
- `build_deck.py` 用 Python 3.13 环境中的 `python-pptx` 生成 PPTX。构建脚本内文字、图形、条件矩阵和柱图均为独立可编辑 PowerPoint 对象；插图单独嵌入。
- PowerPoint COM 渲染与像素级视觉验收由主智能体串行执行。此处不预先宣称已通过渲染验收。


## 当前归档文件

- [deck-草稿.pptx](deck-草稿.pptx)：SHA-256 `aae978a1aae3452ce61f91eee908f0be5f6564d502d869f4aa0e1f334b6cb042`
- [build_deck.py](build_deck.py)：SHA-256 `dadb991b9093ac09ebf98af6b2fbc6db973faadd7bfb68795844fcc3667a682b`
- 页面预览、机器结构证据和人工视觉性质的代理检查分别见 [总览](preview/contact-sheet.jpg)、[机器记录](qa-machine.json)、[验收](qa.md)。
- 构建脚本用于此独立展示项目；复制目录后修改，运行会在同目录重建草稿。原生条形图使用可编辑形状，PNG 插画内部是整张图片。
