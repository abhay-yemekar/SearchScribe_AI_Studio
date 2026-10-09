import Link from "next/link";
import { ArrowDown, ArrowRight, ArrowUpRight } from "lucide-react";
import SiteChrome from "@/components/marketing/SiteChrome";
import {
  HeroDraft,
  StudioStory,
  RewriteShowcase,
} from "@/components/marketing/StudioScenes";

const tools = [
  [
    "01",
    "Find your first draft.",
    "A topic becomes a structured article. Get past the blank page, then make it yours.",
  ],
  [
    "02",
    "Keep the final say.",
    "Edit sections, refine SEO details, and choose a rewrite style. Your judgment stays in charge.",
  ],
  [
    "03",
    "Leave room to change.",
    "Compare versions, restore a previous draft, and export sanitized HTML for your publishing workflow.",
  ],
];

export default function HomePage() {
  return (
    <SiteChrome>
      <section className="hero section-container">
        <div className="hero-topline">
          <p className="eyebrow">[ A writing studio. An open source. ]</p>
          <span className="eyebrow hero-edition">Independent by design / beta</span>
        </div>
        <h1 className="hero-title">
          Start with
          <br />a{" "}
          <span className="thought-word">
            thought.
            <span className="thought-caret" aria-hidden />
          </span>
          <br />
          <span className="hero-title-muted">Leave with a draft.</span>
        </h1>
        <div className="hero-bottom">
          <div className="hero-intro">
            <p>
              An idea is a beginning.
              <br />
              Give it structure, find its voice,
              <br />
              and make it worth reading.
            </p>
            <div className="hero-actions">
              <Link className="button" href="/login?mode=signup">
                Start writing
                <ArrowUpRight size={20} aria-hidden />
              </Link>
              <a className="text-link" href="#the-process">
                Explore the studio
                <ArrowDown size={16} aria-hidden />
              </a>
            </div>
            <p className="beta-note">
              Free, noncommercial beta · Password &amp; Google sign-in
            </p>
          </div>
          <HeroDraft />
        </div>
        <div className="hero-index">
          <span className="eyebrow">
            <span className="status-dot" /> Human ideas. Editorial control.
          </span>
          <span className="eyebrow">Scroll to unfold ↓</span>
        </div>
      </section>
      <section className="manifesto section-container" data-reveal>
        <p className="eyebrow">(01). / A better starting point</p>
        <h2>
          You bring the idea.
          <br />
          We help it <span className="serif-italic">take shape.</span>
          <br />
          <span className="muted">You stay the editor.</span>
        </h2>
        <p className="manifesto-note">
          For bloggers, independent writers, and curious minds. A focused place to draft,
          revise, and prepare an article for publication.
        </p>
      </section>
      <StudioStory />
      <section className="toolkit section-container" data-reveal>
        <div className="section-heading">
          <p className="eyebrow">(03). / The toolkit</p>
          <h2>
            Less friction.
            <br />
            More <span className="serif-italic">intention.</span>
          </h2>
        </div>
        <div className="feature-rows">
          {tools.map(([number, title, text]) => (
            <Link className="feature-row" href="/features" key={number}>
              <span className="eyebrow">[{number}]</span>
              <h3>{title}</h3>
              <p>{text}</p>
              <ArrowUpRight className="feature-arrow" size={28} aria-hidden />
            </Link>
          ))}
        </div>
      </section>
      <RewriteShowcase />
      <section className="open-source section-container" data-reveal>
        <p className="eyebrow">[ Open code. Your words. ]</p>
        <h2>
          A studio you can
          <br />
          <span className="serif-italic">look inside.</span>
        </h2>
        <div className="open-source-detail">
          <p>
            Read the code, run your own instance, or help shape what comes next.
            SearchScribe is an MIT-licensed project. HTML export keeps your article usable
            outside this workspace.
          </p>
          <a
            href="https://github.com/abhay-yemekar/SearchScribe_AI_Studio"
            className="text-link"
          >
            Explore the repository
            <ArrowUpRight size={18} aria-hidden />
          </a>
          <div className="keyboard-detail">
            <span className="eyebrow">A small shortcut</span>
            <p>
              <kbd>Ctrl</kbd> + <kbd>Enter</kbd>{" "}
              <span>Generate from your topic in the studio.</span>
            </p>
          </div>
        </div>
      </section>
      <section className="roadmap section-container" data-reveal>
        <div className="section-heading">
          <p className="eyebrow">(05). / In development</p>
          <h2>Still becoming.</h2>
          <p>
            Built in the open, with a clear line between what works today and what comes
            next.
          </p>
        </div>
        <div className="roadmap-list">
          {[
            ["01", "Research you can trace", "Visible citations and source links."],
            [
              "02",
              "Photos you can credit",
              "Relevant images, credits, and editable alt text.",
            ],
            [
              "03",
              "A more resilient studio",
              "Account recovery, daily quotas, provider fallback, and Markdown export.",
            ],
          ].map(([n, title, detail]) => (
            <div className="roadmap-row" key={n}>
              <span className="eyebrow">[{n}]</span>
              <div>
                <h3>{title}</h3>
                <p>{detail}</p>
              </div>
              <span className="roadmap-tag">In development</span>
            </div>
          ))}
        </div>
        <Link
          href="https://github.com/abhay-yemekar/SearchScribe_AI_Studio"
          className="text-link roadmap-link"
        >
          Follow the open-source project
          <ArrowRight size={18} aria-hidden />
        </Link>
      </section>
      <section className="closing">
        <div className="section-container" data-reveal>
          <p className="eyebrow">(06). / Your next sentence</p>
          <h2>
            Make something
            <br />
            <span className="serif-italic">worth revising.</span>
          </h2>
          <Link className="button button-acid" href="/login?mode=signup">
            Enter the studio
            <ArrowUpRight size={22} aria-hidden />
          </Link>
        </div>
      </section>
      <section className="faq section-container" data-reveal>
        <p className="eyebrow">[ A few things to know ]</p>
        <div>
          {[
            [
              "Is SearchScribe free?",
              "The personal, noncommercial beta is free. Hosting and AI providers have limits, so generation may be temporarily unavailable. No unlimited usage promise.",
            ],
            [
              "Is the draft ready to publish?",
              "It is a starting point. Review facts, originality, tone, and SEO details before publishing. Verified research citations and photo suggestions are still in development.",
            ],
            [
              "Can I use my article elsewhere?",
              "Yes. Preview and download sanitized HTML, then use it in your own publishing workflow. You can also inspect the open-source code or self-host.",
            ],
            [
              "Can I use Google to sign in?",
              "Yes. Google sign-in is deployed alongside password login. To link an existing password account, sign in first and use Account. Password-reset emails are still in development.",
            ],
          ].map(([question, answer]) => (
            <details key={question}>
              <summary>
                {question}
                <span aria-hidden>+</span>
              </summary>
              <p>{answer}</p>
            </details>
          ))}
        </div>
      </section>
    </SiteChrome>
  );
}
