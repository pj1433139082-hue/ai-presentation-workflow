# 六行业展示包

**历史样稿，用户视觉反馈未通过。** 2026-10-12 重构时保留这批 PPTX、渲染与原检查记录；技术通过不等于页面好看。本轮 [三路概念探索](explorations/index.html) 单独记录，还没有转换成 PPTX。下述验收与文件哈希是原样稿归档时的记录，不是对新版入口或改版导航页的验收。

[打开全部 30 页浏览页](index.html) · [返回技能说明](../../README.md)

这批样例演示不同沟通任务的内容结构与视觉表达：科技产品发布、制造业运营复盘、水处理科研方案、健康信息科普、消费品牌提案和社区公共服务。每套 5 页中文 PPTX，比例 16:9，附实际渲染、透明插画、构建脚本、来源和独立代理审查记录。

| 行业与用途 | PPTX | 页面总览 | 来源与验收 |
| --- | --- | --- | --- |
| 科技产品发布 | [下载](tech/deck-草稿.pptx) | [五页](tech/preview/contact-sheet.jpg) | [来源](tech/sources.md) · [验收](tech/qa.md) |
| 制造业经营复盘 | [下载](operations/deck-草稿.pptx) | [五页](operations/preview/contact-sheet.jpg) | [来源](operations/sources.md) · [验收](operations/qa.md) |
| 科研项目汇报 | [下载](research/deck-草稿.pptx) | [五页](research/preview/contact-sheet.jpg) | [来源](research/sources.md) · [验收](research/qa.md) |
| 医疗健康科普 | [下载](health/deck-草稿.pptx) | [五页](health/preview/contact-sheet.jpg) | [来源](health/sources.md) · [验收](health/qa.md) |
| 消费品牌提案 | [下载](brand/deck-草稿.pptx) | [五页](brand/preview/contact-sheet.jpg) | [来源](brand/sources.md) · [验收](brand/qa.md) |
| 公共服务说明 | [下载](public/deck-草稿.pptx) | [五页](public/preview/contact-sheet.jpg) | [来源](public/sources.md) · [验收](public/qa.md) |

## 文件和使用方式

```text
<行业>/
├── deck-草稿.pptx
├── preview/slide-01.png … slide-05.png
├── preview/contact-sheet.jpg
├── assets/*.png
├── build_deck.py
├── sources.md
├── qa.md
├── qa-machine.json
└── review-independent.md
```

数据型样例还附明确标为虚构的数据 CSV。文字、原生形状和示意柱条可以分别修改；PNG 插画可以移动与替换，内部纹理不能逐点编辑。图表由原生形状绘制，不含 Excel 图表系列。

复制整个行业目录后再修改。可直接用 PowerPoint 打开草稿，也可以修改 `build_deck.py` 并用 Python 重建。构建依赖 `python-pptx` 和 Pillow；此次验证使用 Python 3.13.9、python-pptx 1.0.2、Pillow 12。中文字体使用 Microsoft YaHei / Microsoft YaHei UI，健康稿标题使用 Noto Serif SC；其他机器缺字体时可能替换字体并改变折行。重建会覆盖该副本中的草稿与演示 CSV，修改后应重新实际渲染检查。

## 验收范围

三名子智能体分别制作两套，交叉检查他人稿件；主智能体统一用 Microsoft PowerPoint 生成 1920×1080 实际预览，修复并复核问题页，冻结文件后核对哈希。全部 30 页经过逐页代理视觉检查，阻塞性 P0/P1 问题已闭环。少量仅涉及对象框测量余量的 P2 和健康示例标识建议详见对应记录。

源文件与归档文件、PPTX 与预览图、独立报告与当前哈希分别核对。[manifest.json](manifest.json) 记录每套字节数、SHA-256、制作人与独立审查人；[files.sha256.json](files.sha256.json) 记录分发文件清单。

这些是独立本地展示草稿，包含明确标记的虚构品牌、产品、方案和示意数字；不是实际公司业绩、科研结果或已实施服务。健康内容为信息素养科普。代理验收不代表正式项目的人类 G1–G5 批准；此包也不是自动化 validation fixture 或正式生产导出包。
