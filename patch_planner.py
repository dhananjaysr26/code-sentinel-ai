import re
with open("backend/sentinel/graph/context_planner.py", "r") as f:
    content = f.read()

old_loop = """        categories = ["correctness"]
        file_lower = file.lower()
        if any(kw in file_lower for kw in ["auth", "policy", "permission", "crypto", "sql", "db", "security", "login", "models"]):
            categories.append("security")"""

new_loop = """        categories = ["correctness"]
        
        # 1. Filename heuristics
        file_lower = file.lower()
        security_file_kws = ["auth", "policy", "permission", "crypto", "sql", "db", "security", "login", "models"]
        is_security = any(kw in file_lower for kw in security_file_kws)
        
        # 2. Diff content heuristics (for files like utils.py)
        if not is_security:
            # Extract just this file's diff
            file_diff_pattern = r"(?:^|\n)diff --git a/" + re.escape(file) + r" b/.*?(?=\ndiff --git|$)"
            file_diff_match = re.search(file_diff_pattern, raw_diff, re.DOTALL)
            if file_diff_match:
                file_diff = file_diff_match.group(0).lower()
                security_content_kws = [
                    "exec", "eval", "subprocess", "os.system", "popen", 
                    "execute", "query", "cursor", "session.execute",
                    "password", "secret", "token", "jwt", "cookie", "set-cookie",
                    "hash", "md5", "sha", "crypto", "cipher",
                    "redirect", "url", "request", "deserialize", "pickle.loads", "yaml.load"
                ]
                if any(kw in file_diff for kw in security_content_kws):
                    is_security = True
                    
        if is_security:
            categories.append("security")"""

content = content.replace(old_loop, new_loop)
with open("backend/sentinel/graph/context_planner.py", "w") as f:
    f.write(content)
