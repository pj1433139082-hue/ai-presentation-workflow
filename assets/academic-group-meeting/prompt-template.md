# 整页科研概念提示词骨架

先按论文证据填写下列槽位；每页单独调用内置 image_gen，并实际附上已查看的 style-reference/S04.png（或用户另选图）。保留实际传入的最终提示词，不只存此模板。

Use case: scientific-educational.
Create ONE complete Chinese scientific journal-club slide concept.
Input image: actual user-approved scientific style reference, STYLE ONLY.
Match its navy typography, white background, pale-blue scientific panels, translucent explanatory diagrams, restrained gold emphasis and readable information density.
Design the entire page as a coherent scientific explanation. Choose composition from this page's scientific meaning; do not mechanically repeat the reference's flowchart.
Title and visible copy: [当前页确切文案]
Scientific facts, entities and units with sources: [本论文核实内容]
Relationships and directions: [输入/输出/分支/并行证据/反馈的实际关系]
Composition: [本页角色及构图；如有原始证据面板，描述干净留白区域]
Schematic boundary: [哪些图形是示意，哪些是原始证据]
No invented measured plots, spectra, micrographs, numerical results or unsupported causal mechanisms.
Original evidence panels will be inserted unchanged after generation; do not draw quantitative data in reserved windows.
Footer/source and page number: [作者/年份短引用、图号与页码；来源表 source_id 绑定完整书目信息与 DOI/URL]
Use the page number in one place only. Do not repeat the slide index inside the source-citation line.
Requested viewing format: [实际演示比例与观看尺度，不虚构工具没有提供的分辨率参数]

## 局部改图骨架

Edit the attached CURRENT slide concept locally.
Change only: [一个明确可见的问题及预期正确关系/文字/布局]
Preserve: [其他文案、数据、配色、构图、留白窗口等]
Scientific invariants: [必须保持的实体/量值/拓扑]
Do not invent results or redraw original evidence.
Return the complete revised page. Inspect actual changed and untouched regions, and retain both versions.

请求窗口坐标只是意图；合入原图前必须从实际生成图重新确定窗口，保持原图比例和图例完整。

真实证据面板只在生成式编辑结束后合入。合入后仍需局部生图时，编辑无证据的底图并重新叠入原始面板，不将最终含证据的整页交给 image_gen 重画。
