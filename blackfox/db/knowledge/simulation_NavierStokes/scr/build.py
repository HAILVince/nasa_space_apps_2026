# Builds ../habitat_fire_sim.html from app.html + solver.js
import pathlib
here=pathlib.Path(__file__).parent
app=(here/"app.html").read_text(encoding="utf-8"); sol=(here/"solver.js").read_text(encoding="utf-8")
assert "</script" not in sol
out=app.replace("/*__SOLVER__*/", sol)
(here.parent/"habitat_fire_sim.html").write_text(out, encoding="utf-8")
print("built", len(out), "bytes")
