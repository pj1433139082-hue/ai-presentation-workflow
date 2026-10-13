# APW local showcase scaffold

This is an empty draft scaffold. Its presence does not mean a concept, PPTX,
render, agent review, human gate, or release has passed. Fill the canonical
files, then use `scripts/apw.py status` and `scripts/apw.py check`.

`apw init --mode concept|assets|assembly` selects the delivery endpoint;
the default is `concept`. Concept projects finish without an asset manifest,
scene graph or PPTX. Asset projects add declared transparent cutouts and
generation records, while assembly projects additionally need a scene graph,
PPTX, real renders and separate visual review. The selected endpoint is stored
in `delivery-mode.json`. Older projects without it retain the assembly route.

The showcase route is separate from strict production. It must not record
G1–G5 approvals, user visual acceptance, or formal release unless those
decisions actually occur in their proper workflow.
