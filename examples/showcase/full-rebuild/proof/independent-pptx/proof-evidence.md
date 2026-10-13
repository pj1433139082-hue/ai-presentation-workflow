# Independent PPTX reconstruction proof

- Status: built-3-page-independent-proof
- Scope: independent PPTX reconstruction proof outside APW assets-mode endpoint
- Formal assembly acceptance: not-claimed
- Backend: PptxGenJS 4.0.1; rendered by Microsoft PowerPoint COM 16.0.
- Scene: project/scene.json (SHA-256 64782c0d289772caeae10c6b193d7ae44aedd3e2e3530436622299deb72bfe68).
- Source contract: project/reconstruction-map.json and project/asset-manifest.json; 76 generation/source dependencies verified by hash.
- Text fonts: declared Microsoft YaHei UI, Noto Sans SC; observed by PowerPoint Microsoft YaHei UI, Noto Sans SC; font files are not embedded; another system may substitute.
- PPTX: proof/independent-pptx/independent-reconstruction-proof-3pages.pptx (SHA-256 6dd4bf2c740e7960aedff3a3c14d6ddb2390a393f307bbb711ad2f6427fc586e).

## PowerPoint reopen and render evidence

- S01: 9 total objects (5 picture objects, 4 editable text boxes); render proof/independent-pptx/powerpoint-renders/S01.png (SHA-256 9acf698f54bbb7bd362e67f3a9f0c9b15d8c70ea03bc6d7b63d705e67a03dfd4).
- S02: 45 total objects (37 picture objects, 8 editable text boxes); render proof/independent-pptx/powerpoint-renders/S02.png (SHA-256 039c78cbf873f6aadcfe6247fff853ccef65eec24ba5b19af1da9328ed0d4b11).
- S03: 12 total objects (7 picture objects, 5 editable text boxes); render proof/independent-pptx/powerpoint-renders/S03.png (SHA-256 243b17c12c729c7d9382d7e29327072c6e78c0616fea77fd86b38a24d92c6fbe).

## Copy-only editability experiment

- Status: passed; PowerPoint 16.0.
- Native text edit saved and reopened: True; picture move/Undo restored its original position: True.
- Evidence: proof/independent-pptx/editability-test.json (SHA-256 d24b6ced23722c83412b13444f0723ebd9f5aecc9429bc86defd7314d48ec22b); source PPTX hash matched this report.

The builder binds item sources by SHA-256 and confirms they are embedded in the PPTX. Counts and file bindings do not establish visual faithfulness or prove that no scene element was omitted.
