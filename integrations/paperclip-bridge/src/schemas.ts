import { z } from "zod";

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const ServiceType = z.enum([
  "website_landing",
  "website_ecommerce",
  "website_portfolio",
  "webapp_saas",
  "webapp_internal_tool",
  "webapp_dashboard",
  "automation_email",
  "automation_crm",
  "automation_data_pipeline",
  "automation_scraper",
  "automation_reporting",
]);
export type ServiceType = z.infer<typeof ServiceType>;

export const Priority = z.enum(["low", "normal", "high", "urgent"]);
export type Priority = z.infer<typeof Priority>;

export const ProjectStatus = z.enum([
  "received",
  "scoping",
  "in_progress",
  "review",
  "delivered",
  "revision_requested",
  "completed",
  "cancelled",
]);
export type ProjectStatus = z.infer<typeof ProjectStatus>;

// ---------------------------------------------------------------------------
// Project Request (received FROM Aura via TPCP)
// ---------------------------------------------------------------------------

export const ProjectRequest = z.object({
  request_id: z.string().uuid(),
  lead_id: z.string(),
  company_name: z.string().max(255),
  contact_email: z.string().email(),
  contact_name: z.string().optional(),
  contact_phone: z.string().optional(),
  service_type: ServiceType,
  requirements: z.string(),
  budget_usd: z.number().min(0),
  priority: Priority.default("normal"),
  deadline_iso: z.string().datetime().optional(),
  research_notes: z.string().optional(),
  existing_website: z.string().url().optional(),
  industry: z.string().optional(),
  company_size: z
    .enum(["solo", "2-10", "11-50", "51-200", "200+"])
    .optional(),
  metadata: z.record(z.unknown()).default({}),
});
export type ProjectRequest = z.infer<typeof ProjectRequest>;

// ---------------------------------------------------------------------------
// Project Status Update (sent TO Aura via TPCP)
// ---------------------------------------------------------------------------

export const ProjectStatusUpdate = z.object({
  request_id: z.string().uuid(),
  lead_id: z.string(),
  paperclip_ticket_id: z.string().optional(),
  status: ProjectStatus,
  message: z.string().optional(),
  progress_pct: z.number().int().min(0).max(100).default(0),
  deliverable_url: z.string().url().optional(),
  deliverable_type: z
    .enum(["github_repo", "deployed_url", "zip_download", "notion_doc", "other"])
    .optional(),
  agent_notes: z.string().optional(),
  cost_usd: z.number().optional(),
  updated_at: z.string().datetime().default(() => new Date().toISOString()),
});
export type ProjectStatusUpdate = z.infer<typeof ProjectStatusUpdate>;

// ---------------------------------------------------------------------------
// Paperclip REST API types
// ---------------------------------------------------------------------------

export interface PaperclipTicket {
  id: string;
  title: string;
  description: string;
  status: string;
  assigneeId?: string;
  companyId: string;
  goalId?: string;
  metadata?: Record<string, unknown>;
}

export interface PaperclipCreateTicketRequest {
  title: string;
  description: string;
  companyId: string;
  goalId?: string;
  assigneeId?: string;
  priority?: "low" | "medium" | "high" | "urgent";
  metadata?: Record<string, unknown>;
}
