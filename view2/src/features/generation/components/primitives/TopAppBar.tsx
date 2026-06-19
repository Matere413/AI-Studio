"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { IconButton } from "./IconButton";
import { StatusDot, type StatusDotTone } from "./StatusDot";
import styles from "./TopAppBar.module.css";

export interface TopAppBarTab {
  id: string;
  label: string;
  active?: boolean;
  onSelect: () => void;
}

interface TopAppBarProps {
  title?: string;
  tabs: ReadonlyArray<TopAppBarTab>;
  actions?: ReactNode;
  status: StatusDotTone;
  statusLabel: string;
}

function TabRow({
  tabs,
  onSelect,
  className,
}: {
  tabs: ReadonlyArray<TopAppBarTab>;
  onSelect: (tab: TopAppBarTab) => void;
  className: string;
}) {
  return (
    <nav aria-label="Primary tabs" className={className}>
      {tabs.map((tab) => (
        <button
          aria-current={tab.active ? "page" : undefined}
          className={[styles.tab, tab.active ? styles.tabActive : ""].filter(Boolean).join(" ")}
          key={tab.id}
          onClick={() => onSelect(tab)}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

export function TopAppBar({
  title = "Studio",
  tabs,
  actions,
  status,
  statusLabel,
}: TopAppBarProps) {
  const isDesktop = useMediaQuery(1024);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (isDesktop) {
      setMenuOpen(false);
    }
  }, [isDesktop]);

  const handleTabSelect = (tab: TopAppBarTab) => {
    tab.onSelect();
    setMenuOpen(false);
  };

  return (
    <header className={styles.root}>
      <div className={styles.brand}>
        <div className={styles.brandCopy}>
          <p className={`text-mono text-caps ${styles.eyebrow}`}>I-Studio</p>
          <h1 className={styles.title}>{title}</h1>
        </div>

        <div className={styles.status}>
          <StatusDot status={status} />
          <span className={styles.statusLabel}>{statusLabel}</span>
        </div>
      </div>

      {isDesktop ? (
        <>
          <TabRow className={styles.tabs} onSelect={handleTabSelect} tabs={tabs} />
          <div className={styles.actions}>{actions}</div>
        </>
      ) : (
        <div className={styles.mobileControls}>
          <IconButton
            aria-controls="top-app-bar-menu"
            aria-expanded={menuOpen}
            label="Open navigation menu"
            onClick={() => setMenuOpen((value) => !value)}
          >
            <Menu aria-hidden="true" />
          </IconButton>
        </div>
      )}

      {!isDesktop && menuOpen ? (
        <div className={styles.mobileMenu} id="top-app-bar-menu">
          <TabRow className={styles.mobileMenuTabs} onSelect={handleTabSelect} tabs={tabs} />
          {actions ? <div className={styles.mobileMenuActions}>{actions}</div> : null}
        </div>
      ) : null}
    </header>
  );
}
