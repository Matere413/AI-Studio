// ─── SVG Icon Constants ───────────────────────────────────────
// strokeWidth=1.5 per design-tokens spec — all interface icons use
// thin line strokes. No emoji, no raster, no icon fonts.

import type { ReactNode } from "react";

type IconProps = {
  size?: number;
  className?: string;
};

// ─── Internal SVG Wrapper ─────────────────────────────────────
// Centralizes strokeWidth, viewBox, fill, stroke, sizing, and
// className so each icon only provides its path/children.

function IconSvg({
  size = 16,
  className,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  );
}

export const AgentIcon = ({ size = 16, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M12 2a2 2 0 1 1 0 4 2 2 0 0 1 0-4Z" />
    <path d="M5 8a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h1.5" />
    <path d="M19 8a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-1.5" />
    <path d="M12 14v8" />
    <path d="M9 22h6" />
    <rect x="6" y="8" width="12" height="6" rx="1" />
  </IconSvg>
);

export const SettingsIcon = ({ size = 18, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5h.1a1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
  </IconSvg>
);

export const AttachIcon = ({ size = 18, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="m21.4 11.1-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 1 1-2.8-2.8l8.5-8.5" />
  </IconSvg>
);

export const SendIcon = ({ size = 16, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M22 2 11 13" />
    <path d="m22 2-7 20-4-9-9-4Z" />
  </IconSvg>
);

export const SearchIcon = ({ size = 14, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </IconSvg>
);

export const FitToScreenIcon = ({ size = 14, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M15 3h6v6" />
    <path d="M9 21H3v-6" />
    <path d="M21 3l-7 7" />
    <path d="M3 21l7-7" />
  </IconSvg>
);

export const ImageIcon = ({ size = 16, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <path d="m21 15-5-5L5 21" />
  </IconSvg>
);

export const FileIcon = ({ size = 16, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
    <path d="M14 2v6h6" />
  </IconSvg>
);

export const ColumnsIcon = ({ size = 14, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M9 3v18" />
  </IconSvg>
);

export const PlusIcon = ({ size = 16, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </IconSvg>
);

export const ChevronDownIcon = ({ size = 12, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="m6 9 6 6 6-6" />
  </IconSvg>
);

export const CloseIcon = ({ size = 16, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </IconSvg>
);

export const ExportIcon = ({ size = 14, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </IconSvg>
);
