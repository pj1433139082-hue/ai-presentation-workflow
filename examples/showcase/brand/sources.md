# 来源与事实映射｜消费品牌提案

## 示例边界

“山间茶事”和“雾岭春芽”均为本展示稿的虚构名称。包装、场景、详情页、试饮台和赠礼卡均是设计提案，不对应真实品牌、商品、产地、茶类、销量、商店、活动或供应链。本 deck 未使用外部统计、市场规模、消费者调研、产品功效或行业数据；出现的使用时刻是待验证的设计假设。空白字段不代表真实产品信息。

## 逐页内容依据

| 页 | 页面内容 | 依据与边界 |
| --- | --- | --- |
| 01 | 山间茶事新品包装与触点提案封面 | 虚构品牌和虚构 SKU；不表示已上市。 |
| 02 | 轻装出门、午后独处、顺手赠礼三种使用时刻 | 设计假设，必须由真实访谈/试用调整；不是调研结果。 |
| 03 | 礼赠套盒、日常小罐、初次试饮三种包装轮廓 | PowerPoint 原生形状；规格、材料、净含量与标签内容均待确认。 |
| 04 | 产品详情页、线下试饮点、赠礼小卡触点路径 | 概念版式；没有真实购买入口、二维码、店铺或活动。 |
| 05 | 定信息、试结构、看反馈的推进建议 | 建议清单；不承诺成本、时间、销量或试点结果。 |

## 独立视觉组件

- 文件：assets/tea-branch.png
- 角色：封面上的单幅茶枝与山雾插画，作为一个整体透明 PNG 对象放置。
- 生成方式：Codex 内置 image_gen，单次调用生成单一插画组件；没有把整页生成图铺成幻灯片背景。
- 原始提示词：One isolated transparent PNG decorative component for a premium Chinese tea packaging proposal: a graceful tea twig with several fresh leaves and one unopened bud, with a faint hand-painted distant mountain contour behind it. Warm editorial watercolor and fine ink, restrained terracotta and deep tea-green accents, compact horizontal silhouette, generous transparent padding, no ground plane, no shadow, no text, no Chinese characters, no logo, no packaging, no border, not a full-page layout. Transparent alpha background.
- PNG 尺寸：1536×1024；SHA-256：31cf787d86e29acde2cef152ac1477ab39f7907e8167e3e56d5b83db296230a3；完全透明像素约 64.75%。
- 编辑范围：PPTX 中可选中、缩放和移动整张插画；内部叶片、山峦与雾光不是独立矢量对象，不能承诺逐叶修改。


## 当前归档文件

- [deck-草稿.pptx](deck-草稿.pptx)：SHA-256 `5f4d09bda2dcf8a834bd2ed38f778418d86ac0ac872c916604f417d694a3463a`
- [build_deck.py](build_deck.py)：SHA-256 `87ffea2e5dc88333fd033d218d254124731545afc0e584c5b0e9313467490503`
- 页面预览、机器结构证据和人工视觉性质的代理检查分别见 [总览](preview/contact-sheet.jpg)、[机器记录](qa-machine.json)、[验收](qa.md)。
- 构建脚本用于此独立展示项目；复制目录后修改，运行会在同目录重建草稿。原生条形图使用可编辑形状，PNG 插画内部是整张图片。
