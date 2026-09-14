import { z } from "zod";

// 1. Header Block (Title, Severity, File path)
export const HeaderBlockSchema = z.object({
  type: z.literal("header"),
  title: z.string(),
  severity: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
  file: z.string(),
  line: z.number().nullable().optional(),
});

// 2. Diff Block (The exact vulnerable code snippet)
export const DiffBlockSchema = z.object({
  type: z.literal("diff"),
  evidence: z.string(),
});

// 3. Rationale Block (Expandable explanation)
export const RationaleBlockSchema = z.object({
  type: z.literal("rationale"),
  explanation: z.string(),
  suggested_fix: z.string().nullable().optional(),
});

// 4. Metadata Block (Confidence score and source)
export const MetadataBlockSchema = z.object({
  type: z.literal("metadata"),
  confidence: z.number(),
  source: z.string(),
  category: z.string(),
});

// Any Block
export const BlockSchema = z.discriminatedUnion("type", [
  HeaderBlockSchema,
  DiffBlockSchema,
  RationaleBlockSchema,
  MetadataBlockSchema,
]);

export type HeaderBlock = z.infer<typeof HeaderBlockSchema>;
export type DiffBlock = z.infer<typeof DiffBlockSchema>;
export type RationaleBlock = z.infer<typeof RationaleBlockSchema>;
export type MetadataBlock = z.infer<typeof MetadataBlockSchema>;
export type Block = z.infer<typeof BlockSchema>;

// The frontend "Finding" is now composed of these blocks
export const StructuredFindingSchema = z.object({
  id: z.string().uuid(),
  blocks: z.array(z.any()), // Will parse individually in the component
});
