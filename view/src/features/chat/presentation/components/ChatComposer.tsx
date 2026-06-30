"use client";

import { useCallback, useRef, useState } from "react";
import { AttachIcon, IconButton, PillSelect, SendIcon } from "@/shared/presentation";
import type { OrchestrateStage, WorkflowName } from "@/features/chat/domain/dto";
import { getSidebarTabs, getStageTimelineItems, shouldShowManualControls, type SidebarTabId } from "./orchestration-ui";

export interface SelectedAssetSummary {
  id: string;
  name: string;
  uploadStatus: string;
}

export interface ChatSubmitState {
  onSend: (prompt: string) => boolean | Promise<boolean>;
  disabled?: boolean;
}

export interface ChatManualControls {
  workflow: WorkflowName;
  onWorkflowChange: (workflow: WorkflowName) => void;
  referenceFaceUrl: string | null;
  onReferenceFaceUrlChange: (url: string | null) => void;
  /** The File selected for flux2_editing reference (null when cleared). */
  editingReferenceFile: File | null;
  /** Called when user selects or clears a reference file for editing. */
  onEditingReferenceFileChange: (file: File | null) => void;
  /** Whether the reference file upload is in progress. */
  isEditingReferenceUploading?: boolean;
  useTurbo: boolean;
  onTurboChange: (useTurbo: boolean) => void;
}

export interface ChatSelectedAssetsState {
  assets?: SelectedAssetSummary[];
}

export interface ChatOrchestrationState {
  stages?: OrchestrateStage[];
}

interface ChatComposerProps {
  submitState: ChatSubmitState;
  manualControls: ChatManualControls;
  selectedAssets?: ChatSelectedAssetsState;
  orchestrationState?: ChatOrchestrationState;
}

const WORKFLOW_LABELS: Record<WorkflowName, string> = {
  flux2_txt2img: "Flux 2 Text to Image",
  flux2_editing: "Flux 2 Editing",
  identidad_gguf: "Identity GGUF",
};

const WORKFLOW_OPTIONS = Object.entries(WORKFLOW_LABELS) as [WorkflowName, string][];

export function ChatComposer({
  submitState,
  manualControls,
  selectedAssets,
  orchestrationState,
}: ChatComposerProps) {
  const { onSend, disabled = false } = submitState;
  const {
    workflow,
    onWorkflowChange,
    referenceFaceUrl,
    onReferenceFaceUrlChange,
    editingReferenceFile,
    onEditingReferenceFileChange,
    isEditingReferenceUploading = false,
    useTurbo,
    onTurboChange,
  } = manualControls;
  const selectedAssetItems = selectedAssets?.assets ?? [];
  const orchestrationStages = orchestrationState?.stages ?? [];
  const [prompt, setPrompt] = useState("");
  const [activeTab, setActiveTab] = useState<SidebarTabId>("chat");

  // Shared submit: trim once, validate, send, clear
  const submit = useCallback(async () => {
    const trimmed = prompt.trim();
    if (trimmed && !disabled) {
      const accepted = await onSend(trimmed);
      if (accepted) setPrompt("");
    }
  }, [prompt, onSend, disabled]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void submit();
      }
    },
    [submit],
  );

  const handleSend = useCallback(() => {
    void submit();
  }, [submit]);

  const editingFileRef = useRef<HTMLInputElement>(null);

  const handleAttach = useCallback(() => {
    // Trigger file picker for flux2_editing reference images
    if (workflow === "flux2_editing" && editingFileRef.current) {
      editingFileRef.current.click();
    }
  }, [workflow]);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      // Replace legacy FileReader/readAsDataURL with R2 upload pipeline.
      // The parent (page.tsx) handles the upload via executeUpload and
      // stores the resulting asset in sessionAssets with uploadStatus.
      onEditingReferenceFileChange(file);
    },
    [onEditingReferenceFileChange],
  );

  const handleWorkflowChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onWorkflowChange(e.target.value as WorkflowName);
    },
    [onWorkflowChange],
  );

  const showIdentityPanel = workflow === "identidad_gguf";
  const showEditingPanel = workflow === "flux2_editing";
  const showTurboToggle = workflow !== "identidad_gguf";
  const showManualControls = shouldShowManualControls(activeTab);
  const tabs = getSidebarTabs(activeTab);

  return (
    <footer className="border-t border-border bg-surface p-4">
      <div className="mb-3 grid grid-cols-2 rounded-full border border-border bg-base p-1" role="tablist" aria-label="Sidebar mode">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={tab.selected}
            className={`rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors duration-studio ${tab.selected ? "bg-accent text-base" : "text-muted hover:text-primary"}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "chat" && (
        <div className="mb-3 space-y-2 rounded-2xl border border-border bg-base px-3 py-2">
          <div className="text-[11px] font-medium tracking-caps text-muted">Selected assets</div>
          {selectedAssetItems.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {selectedAssetItems.map((asset) => (
                <span key={asset.id} className="rounded-full bg-surface px-2 py-1 text-[11px] text-primary">
                  {asset.name} · {asset.uploadStatus}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-muted">Upload or select an asset when your prompt needs a reference.</p>
          )}
          <StageTimeline stages={orchestrationStages} />
        </div>
      )}

      <div className="overflow-hidden rounded-[24px] border border-border bg-base p-2">
        <div className="flex items-start gap-2">
          <IconButton aria-label="Attach File" onClick={handleAttach} disabled={disabled}>
            <AttachIcon size={18} />
          </IconButton>
          <textarea
            className="min-h-[40px] w-full resize-none border-0 bg-transparent py-[10px] text-[13px] text-primary outline-none placeholder:text-muted disabled:opacity-50"
            aria-label="Message Agent"
            rows={1}
            placeholder="Type a message..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />
          <button
            className="ring-offset-base mt-1 flex size-8 flex-shrink-0 items-center justify-center rounded-full bg-accent text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Send Message"
            onClick={handleSend}
            disabled={disabled || !prompt.trim()}
          >
            <SendIcon size={16} />
          </button>
        </div>
        {showManualControls && <div className="flex flex-wrap gap-2 px-2 pb-1 pt-0.5">
          <PillSelect
            aria-label="Workflow"
            value={workflow}
            onChange={handleWorkflowChange}
            disabled={disabled}
          >
            {WORKFLOW_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </PillSelect>
          {showTurboToggle && (
            <PillSelect
              aria-label="Generation Speed"
              value={useTurbo ? "turbo" : "balanced"}
              onChange={(e) => onTurboChange(e.target.value === "turbo")}
              disabled={disabled}
            >
              <option value="balanced">Balanced</option>
              <option value="turbo">Turbo</option>
            </PillSelect>
          )}
        </div>}
      </div>

      {/* Identity reference panel — shown only for identidad_gguf */}
      {showManualControls && showIdentityPanel && (
        <div className="mt-2 flex items-center gap-2 rounded-xl border border-border bg-base px-3 py-2">
          <input
            className="min-w-0 flex-1 border-0 bg-transparent text-[12px] text-primary outline-none placeholder:text-muted"
            type="text"
            aria-label="Reference Face URL"
            placeholder="Paste reference face image URL..."
            value={referenceFaceUrl ?? ""}
            onChange={(e) =>
              onReferenceFaceUrlChange(e.target.value || null)
            }
          />
          {referenceFaceUrl && (
            <button
              className="text-[11px] font-mono tracking-caps text-muted hover:text-primary transition-colors duration-studio"
              onClick={() => onReferenceFaceUrlChange(null)}
              aria-label="Clear reference URL"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Editing reference panel — shown only for flux2_editing */}
      {showManualControls && showEditingPanel && (
        <div className="mt-2 flex items-center gap-2 rounded-xl border border-border bg-base px-3 py-2">
          <input
            ref={editingFileRef}
            type="file"
            accept="image/*"
            className="hidden"
            aria-label="Select reference image for editing"
            onChange={handleFileSelect}
          />
          <button
            className="flex items-center gap-1.5 rounded-lg bg-accent/10 px-3 py-1.5 text-[12px] font-medium text-accent hover:bg-accent/20 transition-colors duration-studio"
            onClick={() => editingFileRef.current?.click()}
            aria-label="Choose reference image"
          >
            <AttachIcon size={14} />
            {isEditingReferenceUploading
              ? "Uploading…"
              : editingReferenceFile
                ? "Image selected"
                : "Choose image"}
          </button>
          {editingReferenceFile && (
            <>
              <span className="flex-1 truncate text-[11px] text-muted">
                {isEditingReferenceUploading ? "Uploading reference…" : "Reference image ready"}
              </span>
              <button
                className="text-[11px] font-mono tracking-caps text-muted hover:text-primary transition-colors duration-studio"
                onClick={() => onEditingReferenceFileChange(null)}
                aria-label="Clear reference image"
              >
                Clear
              </button>
            </>
          )}
        </div>
      )}
    </footer>
  );
}

function StageTimeline({ stages }: { stages: OrchestrateStage[] }) {
  const items = getStageTimelineItems(stages);

  return (
    <ol aria-label="Orchestration stages" className="space-y-1">
      {items.map((item) => (
        <li key={item.label} className="flex items-center justify-between rounded-xl bg-surface px-2 py-1.5 text-[11px]">
          <span className="text-primary">{item.label}</span>
          <span className="font-mono tracking-caps text-muted">{item.status}</span>
        </li>
      ))}
    </ol>
  );
}
