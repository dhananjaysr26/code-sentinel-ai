with open("frontend/src/schema/blocks.ts", "r") as f:
    content = f.read()

content = content.replace("suggested_fix: z.string().optional(),", "suggested_fix: z.string().nullable().optional(),")

with open("frontend/src/schema/blocks.ts", "w") as f:
    f.write(content)
