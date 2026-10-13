# 来源与事实映射｜公共服务说明

## 示例边界

“社区图书馆服务升级”是虚构城市的服务方案示例；不是某座真实城市、图书馆或主管部门的正式计划。本 deck 没有真实馆址、开放时间、电话、借阅规则、活动安排、预算、时间表、读者数量或服务成效。所提流程、空间分区和试行步骤均为建议，不表示已经上线。所有待填信息明确标为待属地确认。

## 逐页内容依据

| 页 | 页面内容 | 依据与边界 |
| --- | --- | --- |
| 01 | 社区图书馆服务升级封面 | 虚构城市与方案概念；馆舍插画是独立整体对象。 |
| 02 | 查书、预约、取书三步借阅路径 | 拟议流程；检索入口、预约范围、保留期、凭证均待属地确认。 |
| 03 | 儿童共读、安静阅览、借还咨询、活动空间的动线图 | PowerPoint 原生示意图形；不是实际馆舍测绘图或建筑信息。 |
| 04 | 活动公告字段模板与读者查看路径 | 活动名、时间、地点、对象、名额、报名与变更规则均未设定，待属地确认。 |
| 05 | 地址、开放时段、联系渠道、借阅规则核对清单 | 待确认信息与建议步骤，不表示实际运营计划已获批。 |

## 独立视觉组件

- 文件：assets/community-library.png
- 角色：封面上的社区图书馆入口插画，作为一个整体透明 PNG 对象放置。
- 生成方式：Codex 内置 image_gen，单次调用生成单一插画组件；没有把整页生成图铺成幻灯片背景。
- 原始提示词：One isolated transparent PNG illustration component for a public-service explainer slide about a fictional community library. Show a welcoming small neighborhood library entrance as a clean, low-rise architectural illustration: large glass doorway, visible ramp with handrail, a simple tree and a small seated reader silhouette outside. Crisp contemporary public-information design, friendly pale aqua, warm cream, navy, and a small coral accent; flat editorial cut-paper shapes with subtle grain, strong legibility at small size. Compact vertical composition with generous transparent padding; no sign text, no letters, no logos, no address, no numbers, no border, no background scene, not a full-page slide. Transparent alpha background.
- PNG 尺寸：1225×1284；SHA-256：45fc47e40c04a3c844af0840124764212c3e5ce1f282b3cbdd9aa4f75ba6fe5d；完全透明像素约 50.03%。
- 编辑范围：PPTX 中可选中、缩放和移动整张插画；建筑、人物、植物与坡道作为一张图片，不是逐项可编辑矢量对象。
- 边缘检查：透明边缘局部有高饱和绿/珊瑚色像素；实际浅底 PowerPoint 渲染及独立审查未见影响观感的色边。素材保留原始像素，改用其他背景时应重新核视。


## 当前归档文件

- [deck-草稿.pptx](deck-草稿.pptx)：SHA-256 `346ee1a784c207084f6ed5b11db6f38e9061fa76b0111bbae46ffb40fdcc521f`
- [build_deck.py](build_deck.py)：SHA-256 `d213430dc8d643ea170fef0eaef16dbb6b2ce65cbc1ef008a228f34d2fac21f0`
- 页面预览、机器结构证据和人工视觉性质的代理检查分别见 [总览](preview/contact-sheet.jpg)、[机器记录](qa-machine.json)、[验收](qa.md)。
- 构建脚本用于此独立展示项目；复制目录后修改，运行会在同目录重建草稿。原生条形图使用可编辑形状，PNG 插画内部是整张图片。
