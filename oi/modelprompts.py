"""The instructions for the precision model's Claude calls: research, CAD and check (sub-project 6), measuring and
the product-name check (sub-project 7)."""

RESEARCH_PROMPT = """You research the exact physical dimensions of one product so that a CAD model of it can be built.
- Find official numbers first: the manufacturer's technical specifications, data sheets and dimensional drawings published for accessory makers. Use retailer pages only when nothing official exists.
- Use one search for a technical or dimensional drawing of exactly this product, e.g. "<product> dimensional drawing pdf" (many manufacturers publish them for accessory makers).
- Never fetch PDF files with the fetch tool: they are far too large. When your search or fetch results contain a PDF (or an image) with a technical or dimensional drawing of exactly this product, put its URL into "drawing" together with "find": a few words that stand on the right page of that PDF, such as the product name. Only a URL that appeared in your search or fetch results can be opened; the server opens it itself.
- Also find up to 4 photos of exactly this product (model and colour), each taken straight from one side with the whole product in view on a plain background. Prefer the manufacturer's product or press images, else Wikipedia/Wikimedia Commons or large retailers. Only URLs that appeared in your search or fetch results (an image link on a fetched page counts). "view" is "front", "back", "side-front-left" (seen from the side, the front faces left in the picture), "side-front-right" or "top" (seen from above, the front edge at the bottom of the picture).
- Every number needs its origin: "source" is the index of the page in "sources" it came from, and "kind" is "drawing" (read from a technical drawing), "datasheet" (from a specification page) or "estimate" (your own estimate).
- Orientation: the product stands upright with its front towards the viewer; width is x (left to right), height is y (bottom to top), depth is z (back to front).
- measures: up to 30 dimensions in millimetres that matter for a faithful model, for example corner radius, the size and position of a camera bump, buttons, ports, a screen, a lens.
- features: up to 20 short descriptions of visible features with position and size in millimetres.
- Write labels and features in {language}.
- Finish your answer with exactly one ```json block in this form:
{{"size_mm": [width, height, depth] or null, "size_source": index or null, "measures": [{{"label": "...", "value_mm": 0.0, "source": index or null, "kind": "drawing"}}], "features": ["..."], "sources": [{{"title": "...", "url": "https://..."}}], "drawing": {{"url": "https://...", "find": "..."}} or null, "photos": [{{"url": "https://...", "view": "front"}}]}}"""


CAD_PROMPT = """You write an OpenSCAD program (OpenSCAD 2025 with the BOSL2 library) that models one product as faithfully as the measure sheet, the technical drawing and the photo allow.
- Units are millimetres. The origin is the centre of the product; x points right, y up, z towards the viewer. The product stands upright with its front (display, logo side or main face) towards +z.
- The measure sheet comes from research: use its numbers exactly, especially those of kind "drawing" and "datasheet". Where nothing is known, estimate from the photo and your knowledge and say so in "notes".
- One part per visible component (body, display, camera bump, lenses, buttons, ports, grips, sticks, shade, base …), each with its real colour as "#rrggbb" and a name in {language}.
- "shared" holds variables for the main dimensions and helper modules used by several parts; every part is compiled on its own as: include <BOSL2/std.scad>; $fn = 48; shared; part.
- When a part map is given, it was measured on the technical drawing and the reference photos: build every part listed there with exactly that name and inside its measured ranges (millimetres from the centre of the product's box, everything that sticks out included). The reference photos show the real product, one side each.
- When an outline is given (20 bands with the width x and the depth z in millimetres), the product's silhouette must follow it band by band. Build round products (bottles, cans, cups, lamps) with rotate_extrude from these radii.
- Use BOSL2 for rounded edges, chamfers and cut-outs instead of plain cubes: a product should look like the real thing, not like blocks. Holes and recesses are made with difference().
- Never use import(), surface(), include or use statements: the header already includes BOSL2. Keep each part below about 100 000 triangles (no needless high $fn).
- At most 40 parts."""

BOSL2_GUIDE = """BOSL2 cheat sheet (all sizes in mm):
- cuboid([x, y, z], rounding=r, edges="Z" | EDGES_ALL | [TOP+FRONT, …], chamfer=c, anchor=CENTER)  e.g. cuboid([71.5, 146.7, 7.8], rounding=9, edges="Z");
- thin plates with rounded corners (a camera bump, a display glass): linear_extrude(h, center=true) rect([x, y], rounding=r);  more robust than a rounded cuboid that is thinner than its rounding
- cyl(h=h, d=d | d1=, d2=, rounding=r | rounding1=, rounding2=, chamfer=c, anchor=CENTER, orient=UP)  e.g. cyl(h=2, d=13, rounding2=0.5, orient=FWD);
- prismoid(size1=[x, y], size2=[x, y], h=h, rounding=r)  tapered blocks, e.g. a foot or a cap;
- tube(h=h, od=outer, id=inner)  rings around lenses or buttons;
- rect_tube(size=[x, y], wall=w, h=h, rounding=r)  frames;
- offset_sweep(round_corners(path, radius=r), height=h, top=os_circle(r=1), bottom=os_circle(r=1))  rounded extrusions of any outline;
- skin([profile1, profile2, …], z=[z1, z2, …], slices=8)  smooth transitions between cross-sections (grips, handles);
- rotate_extrude($fn=96) polygon([[r, z], …])  turned parts (lamps, bottles, knobs);
- hull() { … }  organic blobs from spheres/cylinders (controller grips);
- difference() { body(); translate([…]) cyl(…); }  holes and recesses;
- position(TOP) / attach(TOP, BOT)  place a child on a face of its parent;
- text3d("SONY", h=0.4, size=6, anchor=CENTER)  raised lettering for logos."""

CHECK_PROMPT = """You check a CAD model of a product against its technical drawing and a photo and correct the OpenSCAD program.
- You see four renders of the current model: "vorn" looks at the front (+z), "hinten" at the back, "rechts" at the right side (+x), "oben" from above at an angle. Then the drawing, the photo, reference photos of the real product, the measure sheet, the part map measured on drawing and photos, the current program, compile errors per part, a size warning and the measured deviations if there are any.
- List concrete deviations in "issues" (wrong proportions, missing or misplaced components, wrong colours, parts that failed to compile), at most 10, in {language}.
- Return only parts that must change or are new (same name replaces a part), "remove" for parts to delete, and "shared" only if the shared code must change (else null).
- The measured deviations compare your parts with the part map: fix every one (move or resize the part, or add a missing part with exactly that name), unless the part map is clearly wrong; then say so in "issues".
- The outline deviations compare your model's width in each height band with the outline measured on the pictures: fix them by reshaping the body, unless the measured outline is clearly wrong; then say so in "issues".
- Fix every compile error. Keep the conventions: millimetres, origin in the centre, y up, front towards +z, BOSL2 is already included, no import(), surface(), include or use.
- Answer "verdict": "good" when nothing important is off any more; then return no parts."""

_CAD_PART = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "color": {"type": "string"}, "scad": {"type": "string"}},
    "required": ["name", "color", "scad"],
    "additionalProperties": False,
}
CAD_SCHEMA = {
    "type": "object",
    "properties": {"shared": {"type": "string"}, "parts": {"type": "array", "items": _CAD_PART},
                   "notes": {"type": "string"}},
    "required": ["shared", "parts", "notes"],
    "additionalProperties": False,
}
CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["good", "fix"]},
        "issues": {"type": "array", "items": {"type": "string"}},
        "shared": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "parts": {"type": "array", "items": _CAD_PART},
        "remove": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "issues", "shared", "parts", "remove"],
    "additionalProperties": False,
}

MEASURE_PROMPT = """You measure the visible parts of one product on technical drawings and reference photos, so that a CAD model can put every part exactly where it is.
- The pictures are numbered from 1. One picture can hold several views of the product: a technical drawing often shows the front, a side and the top next to each other.
- Give every view that shows the whole product straight on (orthographic or nearly so) with "picture", "view" and the boxes. "view" is "front" (looking at the front), "back", "side-front-left" (seen from the side, the front faces left in the picture), "side-front-right" or "top" (seen from above, the front edge at the bottom of the picture).
- Boxes are [left, top, right, bottom] as fractions of the picture's width and height: 0 is the left or top edge, 1 the right or bottom edge. Be as exact as you can: the boxes become millimetres.
- "object" encloses everything of the product in that view, including parts that stick out (sticks, buttons, cables).
- "slices" (front, back and side views): exactly 20 entries from top to bottom. Entry i is the band of the object box from i/20 to (i+1)/20 of its height; give [left, right], the outermost left and right edge of the product's outline within that band, as fractions of the picture's width, or null where an edge is hidden (by a hand, the picture's edge). For top views give [].
- The last picture can be a camera photo of the real object (everything else is grey; it may be tilted or partly covered by a hand). Measure it like the others where it is straight on: it is the only picture that surely shows this very object. In it, an edge counts only where the product meets the grey background; where it meets a hand, clothes or the picture's border, give null.
- "tilt": how many degrees the product's upright axis leans to the right in that view (negative: to the left), 0 when it stands straight. Give the boxes and slices as you see them; the server takes the tilt out.
- "parts": a box around every visible component (buttons, sticks, D-pad, ports, lenses, logos, lights, grips, display …) with a short name in {language}, the way a CAD model would name its parts. Use the same name for the same component in every view.
- Leave out views in perspective, cut off or partly hidden. Dimension lines, arrows and text are not parts.
- At most 6 views and 40 parts per view."""

_BOX = {"type": "array", "items": {"type": "number"}}
MEASURE_SCHEMA = {
    "type": "object",
    "properties": {
        "views": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "picture": {"type": "integer"},
                "view": {"type": "string", "enum": ["front", "back", "side-front-left", "side-front-right", "top"]},
                "object": _BOX,
                "slices": {"type": "array", "items": {"anyOf": [{"type": "null"}, _BOX]}},
                "tilt": {"type": "number"},
                "parts": {"type": "array", "items": {
                    "type": "object", "properties": {"name": {"type": "string"}, "box": _BOX},
                    "required": ["name", "box"], "additionalProperties": False}},
            },
            "required": ["picture", "view", "object", "parts", "slices", "tilt"],
            "additionalProperties": False}},
        "notes": {"type": "string"},
    },
    "required": ["views", "notes"],
    "additionalProperties": False,
}

SAME_PRODUCT_PROMPT = """You decide whether product names mean the same product: the same model and generation, as a CAD model of it would look (the colour does not matter).
- Answer "match" with the exact candidate name that is the same product as the new name, or null if none is or you are not sure."""

SAME_PRODUCT_SCHEMA = {
    "type": "object",
    "properties": {"match": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
    "required": ["match"],
    "additionalProperties": False,
}
