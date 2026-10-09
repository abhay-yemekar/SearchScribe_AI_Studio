"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ArrowUpRight, Menu, Moon, Sun, X } from "lucide-react";
import BrandLogo from "@/components/brand/BrandLogo";
import { useSession } from "@/features/auth/useSession";
import { useHydrated } from "@/lib/useHydrated";

const links = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/features", label: "Features" },
  { href: "/example", label: "Example" },
];

const themeKey = "searchscribe.public-theme";
const themeEvent = "searchscribe-theme-change";
let unavailableStorageTheme: boolean | null = null;

function readDarkTheme() {
  if (unavailableStorageTheme !== null) return unavailableStorageTheme;
  try {
    return localStorage.getItem(themeKey) === "dark";
  } catch {
    return false;
  }
}

function subscribeTheme(listener: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === themeKey || event.key === null) {
      unavailableStorageTheme = null;
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(themeEvent, listener);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(themeEvent, listener);
  };
}

function saveDarkTheme(dark: boolean) {
  try {
    localStorage.setItem(themeKey, dark ? "dark" : "light");
    unavailableStorageTheme = null;
  } catch {
    // The control still works when browser privacy settings prevent storage.
    unavailableStorageTheme = dark;
  }
  window.dispatchEvent(new Event(themeEvent));
}

export default function SiteChrome({ children }: { children: React.ReactNode }) {
  const { user } = useSession({ publicView: true });
  const hydrated = useHydrated();
  const [menuOpen, setMenuOpen] = useState(false);
  const dark = useSyncExternalStore(subscribeTheme, readDarkTheme, () => false);
  const shell = useRef<HTMLDivElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.animate(
            [
              { opacity: 0.35, transform: "translateY(24px)" },
              { opacity: 1, transform: "translateY(0)" },
            ],
            { duration: 700, easing: "cubic-bezier(.22,1,.36,1)" },
          );
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.12 },
    );
    shell.current
      ?.querySelectorAll("[data-reveal]")
      .forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [menuOpen]);

  return (
    <div ref={shell} className="marketing-shell" data-theme={dark ? "dark" : "light"}>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="site-header">
        <div className="site-nav">
          <Link href="/" aria-label="SearchScribe home" className="brand-link">
            <BrandLogo />
          </Link>
          <nav aria-label="Main navigation" className="desktop-nav">
            {links.map((link) => (
              <Link key={link.href} href={link.href}>
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="nav-actions">
            <button
              className="theme-toggle"
              disabled={!hydrated}
              onClick={() => saveDarkTheme(!dark)}
              aria-label={dark ? "Use light theme" : "Use dark theme"}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link href={user ? "/account" : "/login"} className="nav-login">
              {user ? "Account" : "Log in"}
            </Link>
            <Link
              href={user ? "/dashboard" : "/login?mode=signup"}
              className="button button-small nav-cta"
            >
              {user ? "Open workspace" : "Start writing"}
              <ArrowUpRight size={16} aria-hidden />
            </Link>
            <button
              ref={menuButton}
              className="mobile-menu-toggle"
              disabled={!hydrated}
              aria-label={menuOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={menuOpen}
              aria-controls="site-mobile-nav"
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav
            id="site-mobile-nav"
            aria-label="Mobile navigation"
            className="mobile-nav"
            onClick={() => setMenuOpen(false)}
          >
            {links.map((link, index) => (
              <Link key={link.href} href={link.href}>
                <span>0{index + 1}</span>
                {link.label}
                <ArrowUpRight size={20} aria-hidden />
              </Link>
            ))}
            <Link href={user ? "/dashboard" : "/login"}>
              <span>04</span>
              {user ? "Open workspace" : "Log in / Sign up"}
              <ArrowUpRight size={20} aria-hidden />
            </Link>
          </nav>
        )}
      </header>
      <main id="main-content">{children}</main>
      <footer className="site-footer">
        <div className="section-container">
          <div className="footer-top">
            <p>
              A little thought.
              <br />A lot of possibility.
            </p>
            <Link
              className="footer-arrow"
              href={user ? "/dashboard" : "/login?mode=signup"}
              aria-label={user ? "Open workspace" : "Start writing"}
            >
              <ArrowUpRight aria-hidden />
            </Link>
          </div>
          <div className="footer-links">
            <Link href="/" aria-label="SearchScribe home">
              <BrandLogo />
            </Link>
            <nav aria-label="Footer navigation">
              <Link href="/how-it-works">How it works</Link>
              <Link href="/features">Features</Link>
              <Link href="/privacy">Privacy</Link>
              <a
                href="https://github.com/abhay-yemekar/SearchScribe_AI_Studio"
                target="_blank"
                rel="noreferrer"
              >
                GitHub ↗
              </a>
            </nav>
          </div>
          <div className="footer-bottom">
            <span className="eyebrow">
              <span className="status-dot" /> Built in the open
            </span>
            <p>
              Free, noncommercial beta. AI drafts need human review.
              <br />
              Research citations and photo suggestions are in development.
            </p>
            <span className="eyebrow">SearchScribe AI / 2026</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
