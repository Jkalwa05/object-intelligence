// Compiles one part of a precision model (sub-project 6): OpenSCAD 2025 as WebAssembly with the Manifold kernel.
// stdin:  {"code": "<OpenSCAD>", "lib": "<folder that contains BOSL2/>"}
// stdout: {"ok": bool, "stl": "<binary STL, base64>" | null, "triangles": number, "errors": ["ERROR: …", …]}
// OpenSCAD only sees its own in-memory file system: the code cannot read or write files on the Mac.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createOpenSCAD } from "openscad-wasm-prebuilt";

const input = JSON.parse(readFileSync(0, "utf8"));
const errors = [];
const keep = (line) => {
  if (/ERROR|WARNING/.test(String(line)) && errors.length < 20) errors.push(String(line));
};
const scad = (await createOpenSCAD({ print: keep, printErr: keep })).getInstance();
scad.FS.mkdir("/BOSL2");
const lib = join(input.lib, "BOSL2");
for (const name of readdirSync(lib)) {
  if (name.endsWith(".scad")) scad.FS.writeFile(`/BOSL2/${name}`, readFileSync(join(lib, name)));
}
scad.FS.writeFile("/model.scad", input.code);
let stl = null;
try {
  scad.callMain(["/model.scad", "--backend=manifold", "-o", "/out.stl", "--export-format=binstl"]);
  stl = scad.FS.readFile("/out.stl");
} catch (error) {
  keep(`ERROR: ${error}`); // no output file: the collected lines say why
}
const triangles = stl && stl.length >= 84 ? new DataView(stl.buffer, stl.byteOffset).getUint32(80, true) : 0;
process.stdout.write(JSON.stringify({
  ok: stl !== null,
  stl: stl ? Buffer.from(stl).toString("base64") : null,
  triangles,
  errors,
}));
