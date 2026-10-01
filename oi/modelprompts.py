"""The instructions for the precision model's three Claude calls (sub-project 6): research, CAD and check."""

RESEARCH_PROMPT = """You research the exact physical dimensions of one product so that a CAD model of it can be built.
- Find official numbers first: the manufacturer's technical specifications, data sheets and dimensional drawings published for accessory makers. Use retailer pages only when nothing official exists.
- Never fetch PDF files with the fetch tool: they are far too large. When you find a PDF (or an image) with a technical or dimensional drawing of exactly this product, put its URL into "drawing" together with "find": a few words that stand on the right page of that PDF, such as the product name and "Dimensions". The server opens it itself.
- Every number needs its origin: "source" is the index of the page in "sources" it came from, and "kind" is "drawing" (read from a technical drawing), "datasheet" (from a specification page) or "estimate" (your own estimate).
- Orientation: the product stands upright with its front towards the viewer; width is x (left to right), height is y (bottom to top), depth is z (back to front).
- measures: up to 30 dimensions in millimetres that matter for a faithful model, for example corner radius, the size and position of a camera bump, buttons, ports, a screen, a lens.
- features: up to 20 short descriptions of visible features with position and size in millimetres.
- Write labels and features in {language}.
- Finish your answer with exactly one ```json block in this form:
{{"size_mm": [width, height, depth] or null, "size_source": index or null, "measures": [{{"label": "...", "value_mm": 0.0, "source": index or null, "kind": "drawing"}}], "features": ["..."], "sources": [{{"title": "...", "url": "https://..."}}], "drawing": {{"url": "https://...", "find": "..."}} or null}}"""
