# Builds ../habitat_fire_section_2d.html from app2d.html + solver.js (run make_app2d.py first if the 3D app changed)
import pathlib
here=pathlib.Path(__file__).parent
app=(here/"app2d.html").read_text(encoding="utf-8"); sol=(here/"solver.js").read_text(encoding="utf-8")
assert "</script" not in sol
out=app.replace("/*__SOLVER__*/", sol)
(here.parent/"habitat_fire_section_2d.html").write_text(out, encoding="utf-8")
print("built", len(out), "bytes")
