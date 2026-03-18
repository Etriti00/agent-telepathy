import { z } from "zod";

// ---------------------------------------------------------------------------
// xyops API types
// ---------------------------------------------------------------------------

/** A job in xyops. Created via GET /api/app/create_job/v1 */
export const XyopsJob = z.object({
  id: z.string(),
  event_id: z.string().optional(),
  category: z.string().optional(),
  code: z.number().optional(),   // 0 = running, >0 = done, -1 = failed
  progress: z.number().optional(),
  description: z.string().optional(),
  hostname: z.string().optional(),
  created: z.number().optional(),
  modified: z.number().optional(),
});
export type XyopsJob = z.infer<typeof XyopsJob>;

/** xyops job creation params */
export const CreateJobParams = z.object({
  event: z.string(),              // xyops event plugin ID
  params: z.record(z.unknown()).optional(), // Plugin params
  // Optional scheduling (if xyops job is recurring)
  // For one-shot jobs, just call the API once
});
export type CreateJobParams = z.infer<typeof CreateJobParams>;

/** xyops alert creation params */
export const CreateAlertParams = z.object({
  title: z.string(),
  message: z.string().optional(),
  expression: z.string(),         // e.g. "[job.total_errors] > 0"
  group_id: z.string().optional(),
  notify_email: z.string().optional(),
  notify_web_hooks: z.array(z.string()).optional(),
});
export type CreateAlertParams = z.infer<typeof CreateAlertParams>;

/** xyops webhook payload (what xyops POSTs to our webhook endpoint) */
export const XyopsWebhookPayload = z.object({
  id: z.string(),                 // job ID
  event_id: z.string().optional(),
  hostname: z.string().optional(),
  code: z.number(),               // 0 = success, non-zero = error
  description: z.string().optional(),
  progress: z.number().optional(),
  perf: z.record(z.number()).optional(),
  created: z.number().optional(),
  modified: z.number().optional(),
});
export type XyopsWebhookPayload = z.infer<typeof XyopsWebhookPayload>;

// ---------------------------------------------------------------------------
// TPCP → xyops message schemas
// (messages that Aura/Paperclip send to xyops-agent via TPCP)
// ---------------------------------------------------------------------------

/** Request to schedule a one-shot or recurring job in xyops */
export const ScheduleJobRequest = z.object({
  type: z.literal("schedule_job"),
  job_id: z.string().uuid(),           // caller's correlation ID
  event: z.string(),                   // xyops event plugin to run
  params: z.record(z.unknown()).optional(),
  description: z.string().optional(),  // human-readable label for logs
  notify_sender: z.boolean().default(true), // send TPCP update when done
});
export type ScheduleJobRequest = z.infer<typeof ScheduleJobRequest>;

/** Request to create a health alert in xyops */
export const CreateAlertRequest = z.object({
  type: z.literal("create_alert"),
  alert_id: z.string().uuid(),
  title: z.string(),
  expression: z.string(),
  message: z.string().optional(),
});
export type CreateAlertRequest = z.infer<typeof CreateAlertRequest>;

/** Request to get the status of an xyops job */
export const GetJobStatusRequest = z.object({
  type: z.literal("get_job_status"),
  xyops_job_id: z.string(),
});
export type GetJobStatusRequest = z.infer<typeof GetJobStatusRequest>;

// Union of all inbound TPCP messages xyops-agent handles
export const XyopsInboundMessage = z.discriminatedUnion("type", [
  ScheduleJobRequest,
  CreateAlertRequest,
  GetJobStatusRequest,
]);
export type XyopsInboundMessage = z.infer<typeof XyopsInboundMessage>;

// ---------------------------------------------------------------------------
// xyops → TPCP message schemas
// (status updates xyops-agent sends back via TPCP)
// ---------------------------------------------------------------------------

export const JobStatus = z.enum([
  "queued",
  "running",
  "success",
  "error",
  "cancelled",
]);
export type JobStatus = z.infer<typeof JobStatus>;

/** Status update sent back to the requesting agent via TPCP STATE_SYNC */
export const JobStatusUpdate = z.object({
  type: z.literal("job_status_update"),
  job_id: z.string().uuid(),           // caller's correlation ID
  xyops_job_id: z.string(),
  status: JobStatus,
  progress_pct: z.number().int().min(0).max(100).optional(),
  description: z.string().optional(),
  error: z.string().optional(),
  perf: z.record(z.number()).optional(),
  updated_at: z.string().datetime().default(() => new Date().toISOString()),
});
export type JobStatusUpdate = z.infer<typeof JobStatusUpdate>;

/** Health report sent periodically to all agents */
export const AgencyHealthReport = z.object({
  type: z.literal("agency_health"),
  timestamp: z.string().datetime(),
  services: z.record(
    z.enum(["healthy", "degraded", "down"])
  ),
  active_jobs: z.number().int().min(0),
  failed_jobs_24h: z.number().int().min(0),
});
export type AgencyHealthReport = z.infer<typeof AgencyHealthReport>;
