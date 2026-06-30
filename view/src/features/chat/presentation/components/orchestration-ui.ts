import { createOrchestrateStages, type OrchestrateResponse, type OrchestrateStage } from "../../domain/dto.ts";

export type SidebarTabId = "chat" | "manual";

export interface SidebarTab {
  id: SidebarTabId;
  label: string;
  selected: boolean;
}

export interface StageTimelineItem {
  label: string;
  status: string;
}

export function getSidebarTabs(activeTab: SidebarTabId): SidebarTab[] {
  return [
    { id: "chat", label: "Chat", selected: activeTab === "chat" },
    { id: "manual", label: "Manual", selected: activeTab === "manual" },
  ];
}

export function shouldShowManualControls(activeTab: SidebarTabId): boolean {
  return activeTab === "manual";
}

export function getStageTimelineItems(stages: OrchestrateStage[]): StageTimelineItem[] {
  const visibleStages = stages.length > 0 ? stages : createOrchestrateStages();
  return visibleStages.map((stage) => ({
    label: formatStageName(stage.name),
    status: formatStageStatus(stage.status),
  }));
}

export function getSafeOrchestrationMessage(response: OrchestrateResponse): string {
  if (response.outcome === "clarification_required") {
    return response.question ?? "Could you clarify what you want to create?";
  }
  if (response.outcome === "missing_asset") {
    return response.guidance ?? "Upload or select the required asset before generating.";
  }
  if (response.outcome === "error") {
    switch (response.error_code) {
      case "planner_provider_invalid_response":
        return "The planning service returned an invalid response. Please try again.";
      case "planner_provider_unavailable":
      case "timeout":
        return "The planning service is unavailable. Your prompt was not submitted; please try again.";
      case "invalid_orchestration_response":
        return "The orchestration response was invalid. Your prompt was not submitted; please try again.";
      default:
        return "Orchestration failed. Your prompt was not submitted; please try again.";
    }
  }
  return "Generation started.";
}

function formatStageName(name: OrchestrateStage["name"]): string {
  const text = name.split("_").join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatStageStatus(status: OrchestrateStage["status"]): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
