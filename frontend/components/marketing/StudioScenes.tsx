"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Check, FileText, History, MousePointer2 } from "lucide-react";
import { useHydrated } from "@/lib/useHydrated";

const topic = "Things to do in Kerala";

export function HeroDraft() {
  return (
    <div className="hero-draft" aria-label="Illustrative article preview">
      <div className="draft-label eyebrow">
        [ From a spark to a sentence ]<span>01 / 06</span>
      </div>
      <div className="query-strip">
        <span className="query-indicator" aria-hidden />
        <span className="typed-topic">{topic}</span>
        <ArrowRight size={17} aria-hidden />
      </div>
      <div className="draft-paper">
        <div className="paper-meta eyebrow">
          <span>Article draft</span>
          <span className="paper-version">v1</span>
        </div>
        <h2>
          A slower kind
          <br />
          of adventure.
        </h2>
        <p>
          From the quiet backwaters to the hills of Munnar, Kerala invites you to explore
          at your own pace.
        </p>
        <div className="paper-lines" aria-hidden>
          <span />
          <span />
          <span />
        </div>
        <div className="paper-bottom">
          <span>
            <Check size={13} aria-hidden /> Your next draft starts here
          </span>
          <span>↗</span>
        </div>
      </div>
      <span className="editor-cursor" aria-hidden>
        <MousePointer2 size={17} fill="currentColor" />
        You, the editor
      </span>
      <p className="scene-caption">
        Illustrative demo · Sample copy, not researched travel advice.
      </p>
    </div>
  );
}

const steps = [
  {
    name: "Topic",
    title: "Start somewhere.",
    detail:
      "A specific idea gives your draft direction. The blank page doesn't get the last word.",
  },
  {
    name: "Structure",
    title: "Give it a shape.",
    detail:
      "Generate a sectioned article. Review the structure and decide what deserves a place.",
  },
  {
    name: "Draft",
    title: "Make it yours.",
    detail: "Edit each section in the workspace. Keep what works, change what doesn't.",
  },
  {
    name: "SEO",
    title: "Help it be found.",
    detail: "Refine the title, description, and keywords without leaving the article.",
  },
  {
    name: "Versions",
    title: "Change your mind.",
    detail:
      "Save a revision or restore a previous version. Good writing leaves room to try again.",
  },
  {
    name: "Export",
    title: "Take it with you.",
    detail: "Preview and download sanitized HTML. Publish through your own workflow.",
  },
];

export function StudioStory() {
  const hydrated = useHydrated();
  const section = useRef<HTMLElement>(null);
  const manualSelection = useRef(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const media = matchMedia(
      "(min-width: 900px) and (prefers-reduced-motion: no-preference)",
    );
    let frame = 0;
    const update = () => {
      frame = 0;
      if (!media.matches || !section.current) return;
      const rect = section.current.getBoundingClientRect();
      if (rect.top > 120 || rect.bottom < innerHeight) {
        manualSelection.current = false;
        return;
      }
      // Keep a chosen step readable until the visitor leaves this walkthrough.
      if (manualSelection.current) return;
      const progress = Math.max(
        0,
        Math.min(1, (120 - rect.top) / Math.max(1, rect.height - innerHeight)),
      );
      setActive(Math.min(5, Math.floor(progress * 6)));
    };
    const scroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    addEventListener("scroll", scroll, { passive: true });
    addEventListener("resize", scroll);
    return () => {
      removeEventListener("scroll", scroll);
      removeEventListener("resize", scroll);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <section
      className="story-section"
      id="the-process"
      ref={section}
      aria-label="From topic to article"
    >
      <div className="story-sticky section-container">
        <div className="story-heading">
          <p className="eyebrow">(02). / From topic to draft</p>
          <span className="eyebrow">[ {String(active + 1).padStart(2, "0")} / 06 ]</span>
        </div>
        <div className="story-layout">
          <div className="story-copy">
            <h2>{steps[active].title}</h2>
            <p>{steps[active].detail}</p>
            <div
              className="story-controls"
              role="group"
              aria-label="Explore writing steps"
            >
              {steps.map((step, i) => (
                <button
                  key={step.name}
                  disabled={!hydrated}
                  className={active === i ? "active" : ""}
                  onClick={() => {
                    manualSelection.current = true;
                    setActive(i);
                  }}
                  aria-pressed={active === i}
                >
                  <span>0{i + 1}</span>
                  {step.name}
                  <ArrowRight size={16} aria-hidden />
                </button>
              ))}
            </div>
          </div>
          <div className="story-board" data-step={active}>
            <div className="board-top eyebrow">
              <span>SearchScribe / Article studio</span>
              <span>
                <span className="status-dot" /> Demo
              </span>
            </div>
            <div className="story-paper">
              <span className="eyebrow">[ {steps[active].name} ]</span>
              <h3>
                A slower kind
                <br />
                of adventure.
              </h3>
              {active === 0 ? (
                <div className="story-input">
                  {topic}
                  <span aria-hidden>↵</span>
                </div>
              ) : active === 1 ? (
                <ol className="story-outline">
                  <li>The quiet backwaters</li>
                  <li>A morning in Munnar</li>
                  <li>Where the journey goes next</li>
                </ol>
              ) : active === 3 ? (
                <dl className="story-seo">
                  <dt>SEO TITLE</dt>
                  <dd>A first look at Kerala</dd>
                  <dt>DESCRIPTION</dt>
                  <dd>A thoughtful starting point for your Kerala article.</dd>
                  <dt>KEYWORDS</dt>
                  <dd>Kerala · backwaters · Munnar</dd>
                </dl>
              ) : active === 4 ? (
                <div className="story-versions">
                  <p>
                    <History size={18} aria-hidden />
                    Version history
                  </p>
                  <div>
                    <span>v3 / Revised introduction</span>
                    <Check size={15} aria-hidden />
                  </div>
                  <div>
                    <span>v2 / SEO update</span>
                    <span>Restore ↗</span>
                  </div>
                  <div>
                    <span>v1 / First draft</span>
                    <span>Restore ↗</span>
                  </div>
                </div>
              ) : active === 5 ? (
                <div className="story-export">
                  <FileText size={44} strokeWidth={1} aria-hidden />
                  <code>kerala-first-draft.html</code>
                  <span>
                    <Check size={16} aria-hidden /> Ready for your next step
                  </span>
                </div>
              ) : (
                <div className="story-prose">
                  <p>
                    From the quiet backwaters to the hills of Munnar, Kerala invites you
                    to explore at your own pace.
                  </p>
                  <h4>The quiet backwaters</h4>
                  <p>
                    Begin with a place, a detail, a moment. Then build the story you want
                    to tell.
                  </p>
                </div>
              )}
            </div>
            <div className="board-progress" aria-hidden>
              {steps.map((s, i) => (
                <span className={i <= active ? "filled" : ""} key={s.name} />
              ))}
            </div>
            <p className="scene-caption">
              Interactive illustration. No AI request is made by this demo.
            </p>
          </div>
        </div>
        <ol className="mobile-story-summary">
          {steps.map((s) => (
            <li key={s.name}>
              <strong>{s.name}</strong>
              <span>{s.detail}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

const voices = [
  [
    "Professional",
    "Kerala offers a distinctive blend of tranquil backwaters, scenic hills, and rich cultural experiences.",
  ],
  [
    "Casual",
    "A little time on the backwaters, a walk through the hills—Kerala makes slowing down feel easy.",
  ],
  [
    "Gen Z",
    "Backwaters, green hills, and a slower pace. Kerala is giving your next adventure a fresh mood.",
  ],
  [
    "Technical",
    "This sample itinerary groups activities into three categories: waterways, hill landscapes, and cultural exploration.",
  ],
  [
    "Marketing",
    "Find your next story in Kerala, where quiet waterways and green hills invite a different kind of adventure.",
  ],
  ["Minimal", "Quiet water. Green hills. Kerala, at your pace."],
];

export function RewriteShowcase() {
  const hydrated = useHydrated();
  const [voice, setVoice] = useState(0);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <section className="voice-section" data-reveal>
      <div className="section-container">
        <div className="section-heading">
          <p className="eyebrow">(04). / Six rewrite styles</p>
          <h2>
            One idea.
            <br />
            <span className="serif-italic">Different voices.</span>
          </h2>
          <p>Try another tone. Keep your point of view.</p>
        </div>
        <div role="tablist" aria-label="Sample rewrite styles" className="voice-tabs">
          {voices.map(([name], i) => (
            <button
              ref={(el) => {
                buttons.current[i] = el;
              }}
              key={name}
              id={`voice-${i}`}
              role="tab"
              type="button"
              disabled={!hydrated}
              tabIndex={voice === i ? 0 : -1}
              aria-selected={voice === i}
              aria-controls="voice-preview"
              onClick={() => setVoice(i)}
              onKeyDown={(e) => {
                let next = i;
                if (e.key === "ArrowRight") next = (i + 1) % voices.length;
                else if (e.key === "ArrowLeft")
                  next = (i + voices.length - 1) % voices.length;
                else if (e.key === "Home") next = 0;
                else if (e.key === "End") next = voices.length - 1;
                else return;
                e.preventDefault();
                setVoice(next);
                buttons.current[next]?.focus();
              }}
            >
              {name}
            </button>
          ))}
        </div>
        <div
          id="voice-preview"
          role="tabpanel"
          aria-labelledby={`voice-${voice}`}
          tabIndex={0}
          className="voice-preview"
        >
          <span className="quote-mark" aria-hidden>
            “
          </span>
          <p key={voice}>{voices[voice][1]}</p>
          <span className="eyebrow">[{voices[voice][0]} / Editorial sample]</span>
        </div>
        <p className="scene-caption">
          Prewritten examples to illustrate the styles. Actual AI rewrites vary.
        </p>
      </div>
    </section>
  );
}
