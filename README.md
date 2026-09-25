# AI Presentation Workflow

一个面向 Codex 的分阶段 PPT 制作技能：先对齐需求、事实和风格，再用**带真实文字与代表性图片的完整概念图**审定页面，最后拆成可复用的透明 PNG 组件。最终普通文字和数据由原生可编辑对象承载；PPTX 拼装是可选交付，不把整张概念图当作“可编辑 PPT”。

## 适合什么任务

- 从简报、资料或参考 PPT 制作/改造演示文稿，需要明确每阶段输入、输出和人工确认点。
- 希望先看有完整图文的页面效果，再决定版式、视觉风格和内容取舍。
- 需要单独重组人物、插图、箭头、基础形、图表/表格外壳等透明 PNG 组件；表格、图表中的文字和数据留空，供后续填写。
- 需要保留截图、图表和结论的来源与状态，不让生图改写事实。

## 安装与使用

```bash
git clone https://github.com/pj1433139082-hue/ai-presentation-workflow.git
```

将克隆得到的整个 `ai-presentation-workflow` 目录放入你的 Agent 技能目录，例如 `~/.agents/skills/ai-presentation-workflow/`。不同客户端的技能发现路径可能不同，请以该客户端的配置为准。技能入口是 [SKILL.md](SKILL.md)；实际生图依赖 Codex 内置 `image_gen` 和可用的 `imagegen` 子技能，不会静默改用其他服务。

在 Codex 中可这样开始：

> 使用 `$ai-presentation-workflow`，先检查我提供的资料，和我确认受众、目标、事实边界与交付形式，然后制作带文字和图片的完整概念图；概念图批准后再拆透明组件。

新项目从 [`assets/project-template/`](assets/project-template/) 复制一份工作目录，填写 `brief.json`、`run-state.json` 等阶段文件。模板中的 `replace-...` 占位内容不能当作真实需求通过入口校验。每完成一个阶段，可运行：

```bash
python scripts/validate_project.py <project-dir> --stage intake
python scripts/validate_project.py <project-dir> --stage concept
python scripts/validate_project.py <project-dir> --stage release
```

只有当前阶段的必需产物、批准记录和哈希关联齐全时才继续。校验器检查结构与证据链，**不能替代逐页人眼审图**。

## 工作流

| 阶段 | 主要产物 | 人工确认 |
| --- | --- | --- |
| 需求与研究 | 简报、资料清单、来源/事实边界 | G1：受众、目标、来源权威性、交付与可编辑要求 |
| 叙事 | 逐页故事线与行动标题 | G2：页面顺序、核心观点和证据映射 |
| 风格与版面 | 参考板、同内容风格校准图、三类锚点、可读性规划 | G3：方向、风格强度、密度、图文展示空间 |
| 完整概念图 | 每页带真实文案和代表性图片的版本化整图、整套联系表 | G4：逐页全尺寸审图、文字/来源、画面与可读性 |
| 母版与组件 | 无普通文字的母版、100% 并排复核证据、透明 PNG、摆放清单 | G4 批准后才能制作；逐项检查构图、留白、透明度 |
| 拼装与验收 | 可选 PPTX、QA 报告和交付包 | G5：最终交付确认 |

核心约束：概念图**只用于审定**，不能作为最终整页背景；普通标题、标签、数字和用户数据不烘焙进组件。图表/表格外壳去掉文字、数值和数据编码标记；特殊造型文字需锁定原文并单独获批。主要文字和证据图的可用空间有明确底线，不能靠持续缩小字号或截图蒙混过关。详见 [阶段契约](references/stage-contracts.md)、[人工闸门](references/human-gates.md)、[可读性约束](references/readability-contract.md)和[组件流程](references/component-pipeline.md)。

## 仓库内容

- [`SKILL.md`](SKILL.md)：技能入口与不可跳过的约束。
- [`assets/project-template/`](assets/project-template/)：可复制的项目阶段文件模板。
- [`references/`](references/)：研究、提示词、风格、可读性、组件、拼装与 QA 细则。
- [`scripts/`](scripts/)：项目合约校验及视觉适配脚本。
- [`tests/`](tests/)：合约、适配器与安装一致性测试。

本仓库提供制作流程与校验工具，不附带用户项目素材、最终 PPTX 或生成图片。正式交付仍以当前项目的人工批准和最终 QA 为准。
