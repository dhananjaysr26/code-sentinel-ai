with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    lines = f.readlines()

for i in range(len(lines)):
    if 'final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:' in lines[i]:
        if '\\n\\n{compact_manifest}"' in lines[i+2]:
            lines[i] = lines[i].replace('\\n', '')
            lines[i+1] = ''
            lines[i+2] = '            final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\\n\\n{compact_manifest}"\n'

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.writelines(lines)
