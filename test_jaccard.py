import re

text1 = "Incorrect role checking logic bypasses admin access control The change replaces user.get_active_roles() with user.roles_status, but has_required_role expects an iterable of role names (strings), not a dictionary of role:active pairs. This will always return False because 'admin' is notin the dictionary keys when checking for membership in set(user_roles)."

text2 = "Authorization Bypass via Direct Role Status Access The change removes the call to user.get_active_roles() and directly accesses user.roles_status, which may include inactive or disabled roles. This could allow users with inactive admin roles to gain administrative privileges, bypassing proper authorization controls."

t1 = set(re.findall(r'\b\w+\b', text1.lower()))
t2 = set(re.findall(r'\b\w+\b', text2.lower()))

intersection = len(t1.intersection(t2))
union = len(t1.union(t2))
jaccard = intersection / union if union > 0 else 0

print(f"Jaccard: {jaccard}")
