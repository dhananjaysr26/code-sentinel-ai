import ast
import json

def find_references_in_file(file_path: str, symbol: str) -> list[dict]:
    try:
        with open(file_path, "r") as f:
            content = f.read()
        tree = ast.parse(content)
    except Exception:
        return []
    
    references = []
    
    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node):
            if node.id == symbol:
                kind = "reference"
                if isinstance(node.ctx, ast.Store):
                    kind = "assignment"
                references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": kind})
            self.generic_visit(node)
            
        def visit_FunctionDef(self, node):
            if node.name == symbol:
                references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "definition (function)"})
            self.generic_visit(node)
            
        def visit_ClassDef(self, node):
            if node.name == symbol:
                references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "definition (class)"})
            self.generic_visit(node)
            
        def visit_Call(self, node):
            # check if it's a direct call to the symbol
            if isinstance(node.func, ast.Name) and node.func.id == symbol:
                references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "call"})
                # we don't generic_visit func if we just handled it, but we can just generic_visit the whole node
                # Wait, if we visit Name inside Call, we'll get 'reference'. We can avoid duplicates later or just handle it.
            elif isinstance(node.func, ast.Attribute) and node.func.attr == symbol:
                references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "method call"})
            self.generic_visit(node)
            
        def visit_Attribute(self, node):
            if node.attr == symbol:
                references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "attribute"})
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name.split('.')[0] == symbol or alias.name == symbol or alias.asname == symbol:
                    references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "import"})
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name == symbol or alias.asname == symbol:
                    references.append({"file": file_path, "line": node.lineno, "column": node.col_offset, "kind": "import"})
            self.generic_visit(node)
            
    Visitor().visit(tree)
    
    # Deduplicate since we might have multiple matches for the same line/col (e.g. Call and Name)
    unique = []
    seen = set()
    for ref in references:
        key = (ref["line"], ref["column"])
        if key not in seen:
            seen.add(key)
            unique.append(ref)
            
    return unique

print(json.dumps(find_references_in_file("server.py", "mcp"), indent=2))
