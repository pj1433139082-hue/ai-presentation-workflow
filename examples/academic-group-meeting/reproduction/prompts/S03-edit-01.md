Revise the attached S03 concept slide to correct the scientific flow while preserving its navy/blue/gold style, page structure, footer, citation, and main title/key takeaway. This attached image is the only image input. Do not add measured graphs or numerical claims.

Correct the model distinction clearly: the pre-trained AESC representation receives only the 20-dimensional cation-composition encoding. Remove “反应条件” from the AESC input. Show OER activity/overpotential labels as the supervised target for the downstream prediction stage; testing conditions may appear only as experiment context, not as AESC composition input.

Make the model path visibly complete: composition encoding → AESC embedding → clusters → local predictors → global ensemble → candidate experiment. Make “局部预测 → 全局集成” readable as a relationship, not only as a cluster scatter.

Correct the active-learning feedback loop: experimental PSCF results are cation-encoded/embedded and added to training sets for the local and global regressors in the next round. Label this return “更新局部/全局回归器”; point it to the downstream prediction branch. Do not point it back to, or imply retraining of, AESC. Mark all explanatory drawings “示意”. Preserve the original exact title “本文把组成迁移、局部建模与全局集成连起来” and key takeaway “额外数据进入表示学习，OER 标签负责下游活性预测”.
