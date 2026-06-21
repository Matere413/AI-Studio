// ─── Chat Domain Barrel ───────────────────────────────────────

export type {
  WorkflowName,
  Flux2Txt2ImgRequest,
  Flux2EditingRequest,
  IdentidadGgufRequest,
  GenerateRequest,
  ValidationResult,
  AllowedFieldsByWorkflow,
} from "./dto";

export { validateRequest } from "./dto";

export type { ChatMessage } from "./chat-message";
