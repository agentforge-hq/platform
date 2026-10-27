"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { brandTagline, brandTaglineLines } from "@/lib/brand";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  CaretDown,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  MagnifyingGlass,
  Plus,
  Sparkle,
  X,
} from "@phosphor-icons/react";
import {
  catalogResponseSchema,
  searchResponseSchema,
  type Catalog,
  type Harness,
  type SearchResponse,
  type Skill,
} from "@/lib/contracts";

type SearchState =
  | { kind: "idle" }
  | { kind: "loading"; query: string }
  | { kind: "success"; query: string; response: SearchResponse }
  | { kind: "error"; query: string; message: string };
type CatalogState =
  | { kind: "loading" }
  | { kind: "ready"; catalog: Catalog }
  | { kind: "error" };
const examples = [
  "Make my writing sound like me",
  "Design a better landing page",
  "Find the root cause of a bug",
];
const categories = [
  "All skills",
  "Design",
  "Engineering",
  "Writing",
  "Research",
  "Operations",
];
const downloadTargets = [
  { label: "macOS · Apple Silicon", file: "darwin-arm64" },
  { label: "macOS · Intel", file: "darwin-amd64" },
  { label: "Linux · x64", file: "linux-amd64" },
  { label: "Linux · ARM64", file: "linux-arm64" },
  { label: "Windows · x64", file: "windows-amd64" },
  { label: "Windows · ARM64", file: "windows-arm64" },
];
const downloadBase =
  "https://github.com/agentforge-hq/agentforge/releases/download/discovery-preview-20261026";
const categoryLetters: Record<string, string> = {
  Design: "D",
  Engineering: "E",
  Writing: "W",
  Research: "R",
  Operations: "O",
  General: "G",
};
const questions = [
  [
    "What is a skill?",
    "A skill is a set of instructions and supporting resources that teaches an agent a specific workflow. It can help with everything from reviewing code to preparing a presentation.",
  ],
  [
    "Do I need to know which skill to look for?",
    "No. Describe what you want to accomplish. Search matches your intent against skill descriptions and example requests, so you can discover capabilities without knowing their names.",
  ],
  [
    "What happens after I install AgentForge?",
    "The discovery skill tells your agent when and how to search this catalog. It can suggest relevant skills during a task. Automatic invocation depends on your harness and its instructions; installation does not guarantee a search on every turn.",
  ],
  [
    "Where do the skills come from?",
    "The initial catalog indexes public skill repositories. Every result links to its original author and a pinned source revision. We maintain the index; the original authors maintain their skills.",
  ],
  [
    "Does every skill work in every harness?",
    "Compatibility varies. We show the available evidence and mark untested support as unknown. Review any scripts, required tools, and credentials before adopting a skill.",
  ],
  [
    "Is browsing free, and what happens to my query?",
    "Browsing does not require an account. The service uses your query for retrieval, without storing a conversation or uploading your repository. Read the privacy page for the current data handling.",
  ],
];

function Mark() {
  return (
    <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="10" fill="currentColor" />
      <path
        d="M10 28V17l10-7 10 7v11M10 20l10 7 10-7M20 10v17"
        stroke="var(--paper)"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function skillTitle(name: string) {
  return name.replace(/^vercel-/, "").replace(/[-_]/g, " ");
}
function sourceName(source: string) {
  return source.split("/")[0] ?? source;
}

function SkillRow({ skill }: { skill: Skill }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState<"idle" | "done" | "error">("idle");
  const detailsId = useId();
  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(
        `Inspect the ${skill.name} skill at ${skill.source.url}. Explain what it does, its requirements, and whether it fits my task before installing it. Keep the pinned revision ${skill.source.revision}.`,
      );
      setCopied("done");
      setTimeout(() => setCopied("idle"), 2400);
    } catch {
      setCopied("error");
    }
  }
  return (
    <article className={`skill-row ${expanded ? "expanded" : ""}`}>
      <div
        className={`category-mark category-${skill.category.toLowerCase()}`}
        aria-hidden="true"
      >
        {categoryLetters[skill.category] ?? "S"}
      </div>
      <div className="skill-content">
        <div className="skill-title-line">
          <h3>
            <button
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              aria-controls={detailsId}
            >
              {skillTitle(skill.name)}
            </button>
          </h3>
          <span className="publisher">
            {sourceName(skill.source.repository)}
          </span>
        </div>
        <p className="skill-summary">{skill.summary}</p>
        <div className="skill-tags">
          <span>{skill.category}</span>
          <span className="source-tag">
            <CheckCircle size={13} /> Pinned source
          </span>
          {skill.license.identifier && <span>{skill.license.identifier}</span>}
        </div>
      </div>
      <button
        className="row-toggle"
        aria-label={`${expanded ? "Collapse" : "Explore"} ${skill.name}`}
        aria-expanded={expanded}
        aria-controls={detailsId}
        onClick={() => setExpanded(!expanded)}
      >
        <CaretDown size={20} aria-hidden="true" />
      </button>
      <div className="skill-detail-region" id={detailsId} hidden={!expanded}>
        {expanded && (
          <div className="skill-details">
            <div>
              <h4>Try asking</h4>
              {skill.example_prompts.map((prompt) => (
                <p className="example-request" key={prompt}>
                  “{prompt}”
                </p>
              ))}
            </div>
            <div>
              <h4>Before you use it</h4>
              <p>
                {skill.requirements.length
                  ? skill.requirements.join(" ")
                  : "Review the source instructions and any supporting scripts before adopting this skill."}
              </p>
              <p>
                Harness compatibility: {skill.compatibility.status}.{" "}
                {skill.adoption_status === "metadata_only"
                  ? "License information is incomplete. Visit the author’s source for details."
                  : "Installation requires a review of the package."}
              </p>
            </div>
            <div className="detail-footer">
              <span>
                Source checked{" "}
                {new Date(skill.source.checked_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC",
                })}{" "}
                · Revision <code>{skill.source.revision.slice(0, 7)}</code>
              </span>
              <div className="detail-actions">
                <button className="text-button" onClick={copyPrompt}>
                  {copied === "done" ? <Check size={16} /> : <Copy size={16} />}
                  {copied === "done" ? "Prompt copied" : "Copy review prompt"}
                </button>
                <a
                  href={skill.source.url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  View source <ArrowUpRight size={16} />
                </a>
              </div>
            </div>
            <p className="review-copy-status" role="status">
              {copied === "error"
                ? "Could not copy the prompt. Open the source to review this skill."
                : copied === "done"
                  ? "Paste the review prompt into your agent."
                  : ""}
            </p>
          </div>
        )}
      </div>
    </article>
  );
}

function CatalogSkeleton({ label }: { label: string }) {
  return (
    <div className="catalog-loading">
      <p className="loading-label">{label}</p>
      <div className="skeleton-list" aria-hidden="true">
        {[0, 1, 2].map((row) => (
          <div className="skeleton-row" key={row}>
            <span className="skeleton-mark" />
            <div className="skeleton-content">
              <span className="skeleton-title" />
              <span className="skeleton-line" />
              <span className="skeleton-meta" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Discovery() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All skills");
  const [harness, setHarness] = useState<Harness>("codex");
  const [search, setSearch] = useState<SearchState>({ kind: "idle" });
  const [catalog, setCatalog] = useState<CatalogState>({ kind: "loading" });
  const [visible, setVisible] = useState(8);
  const [copied, setCopied] = useState<"idle" | "done" | "error">("idle");
  const [downloadOrigin, setDownloadOrigin] = useState("");
  const [downloadTarget, setDownloadTarget] = useState("darwin-arm64");
  const downloadUrl = `${downloadBase}/agentforge-v0.1.0-${downloadTarget}.zip`;
  const [revealed, setRevealed] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const results = useRef<HTMLDivElement>(null);
  const statement = useRef<HTMLHeadingElement>(null);
  const requestNumber = useRef(0);

  useEffect(() => {
    setDownloadOrigin(window.location.origin);
    const controller = new AbortController();
    fetch("/api/v1/catalog", { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error("unavailable");
        const data: unknown = await r.json();
        setCatalog({
          kind: "ready",
          catalog: catalogResponseSchema.parse(data),
        });
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalog({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const element = statement.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setRevealed(true);
          observer.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  async function runSearch(value: string) {
    const text = value.trim();
    if (!text) {
      searchInput.current?.focus();
      return;
    }
    if (new TextEncoder().encode(text).length > 2048) {
      setSearch({
        kind: "error",
        query: text,
        message: "Keep your request under 2,048 bytes.",
      });
      return;
    }
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    const number = ++requestNumber.current;
    setQuery(text);
    setSearch({ kind: "loading", query: text });
    try {
      const response = await fetch("/api/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, harness, limit: 12 }),
        signal: controller.signal,
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const message =
          response.status === 429
            ? "You have made several searches. Wait a minute, then try again."
            : "The catalog could not be reached. Your request is still here. Please try again.";
        throw new Error(message);
      }
      const parsed = searchResponseSchema.parse(data);
      if (number === requestNumber.current) {
        setSearch({ kind: "success", query: text, response: parsed });
        setVisible(12);
        setCategory("All skills");
      }
    } catch (error: unknown) {
      if (!controller.signal.aborted && number === requestNumber.current)
        setSearch({
          kind: "error",
          query: text,
          message:
            error instanceof Error
              ? error.message
              : "Search is unavailable. Please try again.",
        });
    }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runSearch(query);
  }
  function resetSearch() {
    abort.current?.abort();
    requestNumber.current++;
    setSearch({ kind: "idle" });
    setQuery("");
    setVisible(8);
  }
  async function copyInstall() {
    try {
      await navigator.clipboard.writeText(
        `Install the AgentForge skill from ${downloadUrl} in the skill directory supported by my harness. Inspect the archive before installation, preserve any existing skill, and read SKILL.md. Use it to look for useful capabilities when I bring you a new substantive task. Search uses ${downloadOrigin}/api/v1/search; never send my repository or full conversation.`,
      );
      setCopied("done");
      setTimeout(() => setCopied("idle"), 2800);
    } catch {
      setCopied("error");
    }
  }
  const sourceRows =
    search.kind === "success"
      ? search.response.rows
      : catalog.kind === "ready"
        ? catalog.catalog.rows
        : [];
  const filtered =
    category === "All skills"
      ? sourceRows
      : sourceRows.filter((s) => s.category === category);
  const rows = filtered.slice(0, visible);
  const isLoading = search.kind === "loading";

  return (
    <>
      <a className="skip" href="#main">
        Skip to search
      </a>
      <header className="site-header">
        <div className="nav-wrap">
          <Link className="brand" href="/" aria-label="AgentForge home">
            <Mark />
            <span>agentforge</span>
          </Link>
          <nav aria-label="Main">
            <a href="#catalog">Explore skills</a>
            <a
              href="https://github.com/agentforge-hq/company"
              target="_blank"
              rel="noreferrer noopener"
            >
              Building in public <ArrowUpRight size={13} />
            </a>
            <a
              href="#install"
              className="nav-install"
              aria-label="Install AgentForge"
            >
              <span className="nav-install-full">Install AgentForge</span>
              <span className="nav-install-short" aria-hidden="true">
                Install
              </span>
              <ArrowDown size={14} />
            </a>
          </nav>
        </div>
      </header>
      <main id="main">
        <section className="hero container">
          <div className="hero-heading">
            <h1 aria-label={brandTagline}>
              {brandTaglineLines.map((line, index) => (
                <span
                  className={
                    index === 0 ? "hero-tagline-lead" : "hero-tagline-line"
                  }
                  key={line}
                  aria-hidden="true"
                >
                  {line}{" "}
                </span>
              ))}
            </h1>
            <p>
              Describe what you’re trying to do. Discover useful skills,
              <br className="desktop-break" /> and bring a little more know how
              into your agent.
            </p>
          </div>
          <form className="search-form" onSubmit={submit} role="search">
            <label className="sr-only" htmlFor="task-search">
              What are you trying to do?
            </label>
            <MagnifyingGlass className="search-icon" size={23} />
            <input
              ref={searchInput}
              id="task-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What are you trying to do?"
              maxLength={2048}
              autoComplete="off"
            />
            <button
              className="primary search-button"
              type="submit"
              disabled={isLoading}
              aria-label={isLoading ? "Finding skills" : "Find a skill"}
            >
              <span>{isLoading ? "Searching" : "Find a skill"}</span>
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </form>
          <div className="try-queries">
            <span>Try</span>
            {examples.map((text) => (
              <button
                key={text}
                onClick={() => {
                  void runSearch(text);
                  results.current?.scrollIntoView({
                    behavior: "auto",
                    block: "start",
                  });
                }}
              >
                {text}
                <ArrowUpRight size={12} />
              </button>
            ))}
          </div>
          <div className="source-line">
            <span className="live-dot" />
            {catalog.kind === "ready" ? (
              <span>
                {catalog.catalog.skill_count} skill entries from{" "}
                {catalog.catalog.source_count} public repositories. Original
                authors. Pinned sources.
              </span>
            ) : (
              <span>
                A growing index of public skills. Original authors. Pinned
                sources.
              </span>
            )}
          </div>
        </section>

        <section
          className="catalog-section container"
          id="catalog"
          ref={results}
          aria-busy={isLoading}
        >
          <div className="section-heading">
            <div>
              <h2>
                {search.kind === "success" || isLoading
                  ? "A few possibilities for your task"
                  : "A new capability starts here"}
              </h2>
              <p>
                {search.kind === "success"
                  ? `Results for “${search.query}”`
                  : "Explore what your agent could help you do next."}
              </p>
            </div>
            <label className="harness-select">
              Your harness
              <select
                value={harness}
                onChange={(e) => {
                  const result = e.target.value;
                  if (
                    result === "codex" ||
                    result === "claude-code" ||
                    result === "cursor" ||
                    result === "gemini" ||
                    result === "opencode" ||
                    result === "devin" ||
                    result === "portable"
                  )
                    setHarness(result);
                }}
              >
                <option value="codex">Codex</option>
                <option value="claude-code">Claude Code</option>
                <option value="cursor">Cursor</option>
                <option value="gemini">Gemini CLI</option>
                <option value="portable">Any harness</option>
              </select>
            </label>
          </div>
          <div className="catalog-toolbar">
            <div className="categories" aria-label="Skill categories">
              {categories.map((name) => (
                <button
                  className={category === name ? "active" : ""}
                  key={name}
                  onClick={() => {
                    setCategory(name);
                    setVisible(8);
                  }}
                  aria-pressed={category === name}
                >
                  {name}
                </button>
              ))}
            </div>
            {search.kind !== "idle" && (
              <button className="clear-search" onClick={resetSearch}>
                Clear search <X size={14} />
              </button>
            )}
          </div>
          <div className="results-status sr-only" aria-live="polite">
            {isLoading
              ? "Finding relevant skills."
              : search.kind === "error"
                ? search.message
                : search.kind === "idle" && catalog.kind === "loading"
                  ? "Opening the skill catalog."
                  : `${filtered.length} skills available in this view.`}
          </div>
          {((search.kind === "idle" && catalog.kind === "ready") ||
            search.kind === "success") && (
            <p className="catalog-count" aria-hidden="true">
              Showing {rows.length} of {filtered.length}{" "}
              {search.kind === "success" ? "results" : "skills"}
            </p>
          )}
          {isLoading ? (
            <CatalogSkeleton label="Matching your task to useful capabilities…" />
          ) : search.kind === "error" ? (
            <div className="empty-state" role="alert">
              <h3>Search needs another moment.</h3>
              <p>{search.message}</p>
              <button
                className="text-button"
                onClick={() => void runSearch(search.query)}
              >
                Try again <ArrowRight size={16} />
              </button>
            </div>
          ) : catalog.kind === "loading" && search.kind === "idle" ? (
            <CatalogSkeleton label="Opening the skill catalog…" />
          ) : catalog.kind === "error" && search.kind === "idle" ? (
            <div className="empty-state">
              <h3>The catalog is taking a moment.</h3>
              <p>
                You can still install the discovery skill below. Try refreshing
                this page shortly.
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <MagnifyingGlass size={32} />
              <h3>
                {category === "All skills"
                  ? "No useful match this time."
                  : `No ${category.toLowerCase()} skills in this view.`}
              </h3>
              <p>
                Try describing the outcome more specifically, or explore another
                category.
              </p>
              <button
                className="text-button"
                onClick={() => {
                  resetSearch();
                  setCategory("All skills");
                }}
              >
                Explore the catalog <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <div className="skill-list">
              {rows.map((skill) => (
                <SkillRow key={skill.skill_id} skill={skill} />
              ))}
            </div>
          )}
          {filtered.length > visible &&
            !isLoading &&
            search.kind !== "error" && (
              <button
                className="show-more"
                onClick={() => setVisible(visible + 8)}
              >
                Explore more skills <Plus size={16} />
              </button>
            )}
          {search.kind === "success" &&
            search.response.meta.retrieval_mode === "lexical_only" && (
              <p className="mode-note">
                Semantic search is temporarily unavailable. These results use
                keyword matching.
              </p>
            )}
          <div className="catalog-foot">
            <span>
              Capabilities, not guarantees. Review a skill before you use it.
            </span>
            <a
              href="https://github.com/agentforge-hq/company/blob/codex/discovery-search-prd/product/discovery-service-prd.md"
              target="_blank"
              rel="noreferrer noopener"
            >
              How we’re building the index <ArrowUpRight size={13} />
            </a>
          </div>
        </section>

        <section className="install-section" id="install">
          <div className="container install-layout">
            <div className="install-copy">
              <div className="install-mark">
                <Mark />
                <span>One skill. More possibilities.</span>
              </div>
              <h2>
                Let the right skill <br className="desktop-break" />
                find its way into the work.
              </h2>
              <p>
                Install AgentForge once. When you bring a new task, your agent
                can look for useful capabilities and explain what they could
                help you do.
              </p>
              <p className="install-note">
                Designed for agents with terminal access. Automatic discovery
                depends on the harness.
              </p>
              <a href={downloadUrl} className="download-link">
                <DownloadSimple size={18} /> Download the skill{" "}
                <ArrowDown size={14} />
              </a>
            </div>
            <div className="install-panel">
              <div className="install-panel-head">
                <span>Give this to your agent</span>
                <span className="small-label">No API key needed</span>
              </div>
              <p className="install-prompt">
                Install AgentForge and look for useful skills when I bring you a
                new task. Explain what a skill makes possible before offering to
                use it.
              </p>
              <label className="download-select">
                Your platform
                <select
                  value={downloadTarget}
                  onChange={(e) => setDownloadTarget(e.target.value)}
                >
                  {downloadTargets.map((target) => (
                    <option key={target.file} value={target.file}>
                      {target.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="install-source">
                <code>agentforge-v0.1.0-{downloadTarget}.zip</code>
              </div>
              <button className="primary full-width" onClick={copyInstall}>
                {copied === "done" ? <Check size={18} /> : <Copy size={18} />}
                {copied === "done"
                  ? "Setup prompt copied"
                  : copied === "error"
                    ? "Try copying again"
                    : "Copy setup prompt"}
              </button>
              <p className="copy-status" aria-live="polite">
                {copied === "done"
                  ? "Paste it into your agent to inspect and install."
                  : copied === "error"
                    ? "Clipboard access was unavailable. Try again or use Download the skill."
                    : "You choose what gets installed. Your files stay yours."}
              </p>
            </div>
          </div>
        </section>

        <section className="how-section container">
          <div className="section-heading">
            <h2>From a goal to a new possibility.</h2>
            <p>Your agent does the looking. You make the call.</p>
          </div>
          <div className="how-grid">
            <div>
              <MagnifyingGlass size={25} />
              <h3>Start with your task</h3>
              <p>
                Ask for what you want to accomplish. You don’t need skill names,
                tool names, or the right jargon.
              </p>
            </div>
            <div>
              <Sparkle size={25} />
              <h3>See what could help</h3>
              <p>
                Find relevant workflows and understand what they enable, where
                they come from, and what they require.
              </p>
            </div>
            <div>
              <ArrowUpRight size={25} />
              <h3>Bring it into the work</h3>
              <p>
                Choose a skill, review the source, and let your agent use it on
                the task you came to finish.
              </p>
            </div>
          </div>
        </section>
        <section className="statement-section container">
          <h2
            ref={statement}
            className={revealed ? "statement revealed" : "statement"}
            aria-label="You bring the goal. Your agent finds the know how."
          >
            {"You bring the goal. Your agent finds the know how."
              .split(" ")
              .map((word, i) => (
                <span key={i} style={{ transitionDelay: `${i * 35}ms` }}>
                  {word}{" "}
                </span>
              ))}
          </h2>
          <p>
            A shared index of skills. A little more experience within reach.
          </p>
        </section>
        <section className="faq-section container">
          <h2>A few things worth knowing.</h2>
          <div className="faq-list">
            {questions.map(([question, answer]) => (
              <details key={question}>
                <summary>
                  {question}
                  <Plus size={18} />
                </summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
      </main>
      <footer className="site-footer container">
        <div>
          <Link className="brand" href="/">
            <Mark />
            <span>agentforge</span>
          </Link>
          <p>Find what you didn’t know was possible.</p>
        </div>
        <div className="footer-links">
          <a
            href="https://github.com/agentforge-hq/agentforge"
            target="_blank"
            rel="noreferrer noopener"
          >
            Public skill <ArrowUpRight size={13} />
          </a>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <a href="#main">
            Back to search <ArrowUpRight size={13} />
          </a>
        </div>
        <p className="copyright">
          © {new Date().getFullYear()} AgentForge. Platform code and design:
          all rights reserved.
        </p>
      </footer>
    </>
  );
}
