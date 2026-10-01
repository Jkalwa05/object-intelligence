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


CAD_PROMPT = """You write an OpenSCAD program (OpenSCAD 2025 with the BOSL2 library) that models one product as faithfully as the measure sheet, the technical drawing and the photo allow.
- Units are millimetres. The origin is the centre of the product; x points right, y up, z towards the viewer. The product stands upright with its front (display, logo side or main face) towards +z.
- The measure sheet comes from research: use its numbers exactly, especially those of kind "drawing" and "datasheet". Where nothing is known, estimate from the photo and your knowledge and say so in "notes".
- One part per visible component (body, display, camera bump, lenses, buttons, ports, grips, sticks, shade, base …), each with its real colour as "#rrggbb" and a name in {language}.
- "shared" holds variables for the main dimensions and helper modules used by several parts; every part is compiled on its own as: include <BOSL2/std.scad>; $fn = 48; shared; part.
- Use BOSL2 for rounded edges, chamfers and cut-outs instead of plain cubes: a product should look like the real thing, not like blocks. Holes and recesses are made with difference().
- Never use import(), surface(), include or use statements: the header already includes BOSL2. Keep each part below about 100 000 triangles (no needless high $fn).
- At most 40 parts."""

BOSL2_GUIDE = """BOSL2 cheat sheet (all sizes in mm):
- cuboid([x, y, z], rounding=r, edges="Z" | EDGES_ALL | [TOP+FRONT, …], chamfer=c, anchor=CENTER)  e.g. cuboid([71.5, 146.7, 7.8], rounding=9, edges="Z");
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
- You see four renders of the current model: "vorn" looks at the front (+z), "hinten" at the back, "rechts" at the right side (+x), "oben" from above at an angle. Then the drawing, the photo, the measure sheet, the current program, compile errors per part and a size warning if there is one.
- List concrete deviations in "issues" (wrong proportions, missing or misplaced components, wrong colours, parts that failed to compile), at most 10, in {language}.
- Return only parts that must change or are new (same name replaces a part), "remove" for parts to delete, and "shared" only if the shared code must change (else null).
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
