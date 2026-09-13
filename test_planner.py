import sys
sys.path.append("backend")
from sentinel.graph.context_planner import run_context_planner

diff = """diff --git a/test.js b/test.js
index a44e226..142503b 100644
--- a/test.js
+++ b/test.js
@@ -1,7 +1,7 @@
 function calculateTotal(items) {
   let total = 0;
 
-  for (let i = 0; i < items.length; i++) {
+  for (let i = 0; i < items.length - 1; i++) {
     total += items[i].price * items[i].quantity;
   }
"""
evidence = run_context_planner(diff, ["test.js"])
print(evidence.model_dump())
