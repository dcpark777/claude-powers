import React, { useState } from "react";

// ── palette ──────────────────────────────────────────────────────────
const C = {
  bg: "#0B0F16",
  panel: "#121926",
  panelHi: "#18202F",
  line: "#243044",
  text: "#D8DFEA",
  dim: "#7E8BA0",
  faint: "#55617A",
  amber: "#E8A33D",       // needs-you / pending
  amberDim: "#3A2E17",
  cyan: "#4FC3D9",        // info / working
  green: "#58C08A",       // applied / verified
  greenDim: "#15291F",
  red: "#E06565",         // rejected / deletions
  redDim: "#2E1717",
  violet: "#9D8CFF",      // revised
};

const mono = { fontFamily: "'JetBrains Mono','SF Mono',ui-monospace,monospace" };

// ── risk explanations (deterministic heuristics, spelled out) ────────
const RISK_INFO = {
  "config surface":
    "DEFAULTS is read at import time by every backend — a bad value here breaks all writers, not just Snowflake.",
  "hot path":
    "write_df() runs in every scoring-pipeline load. Regressions here hit production jobs, not just this repo.",
};

// ── mock data: dataio session ────────────────────────────────────────
const pendingEdit = {
  file: "dataio/config.py",
  symbol: "DEFAULTS",
  risk: "config surface",
  add: 3, del: 1,
  hunk: [
    { t: "ctx", s: " DEFAULTS = {" },
    { t: "ctx", s: '     "warehouse": "ML_WH",' },
    { t: "del", s: '     "write_timeout_s": 60,' },
    { t: "add", s: '     "write_timeout_s": 120,' },
    { t: "add", s: '     "write_retries": 3,' },
    { t: "add", s: '     "retry_backoff_s": 2.0,' },
    { t: "ctx", s: " }" },
  ],
};

const appliedEdits = [
  {
    file: "dataio/retry.py", badge: "new file", symbol: "with_backoff()",
    add: 41, del: 0, risk: null,
    note: "decorator · exponential backoff, jitter, max 3 attempts",
    hunk: [
      { t: "add", s: "def with_backoff(retries=3, base=2.0):" },
      { t: "add", s: "    def deco(fn):" },
      { t: "add", s: "        @functools.wraps(fn)" },
      { t: "add", s: "        def inner(*a, **kw):" },
      { t: "add", s: "            for attempt in range(retries): ..." },
    ],
  },
  {
    file: "dataio/snowflake/writer.py", badge: null, symbol: "SnowflakeWriter.write_df()",
    add: 12, del: 6, risk: "hot path",
    note: "wraps COPY INTO in with_backoff · surfaces final error unchanged",
    hunk: [
      { t: "ctx", s: "     def write_df(self, df, table):" },
      { t: "del", s: "         self._copy_into(df, table)" },
      { t: "add", s: "         @with_backoff(retries=cfg.write_retries)" },
      { t: "add", s: "         def _attempt():" },
      { t: "add", s: "             self._copy_into(df, table)" },
      { t: "add", s: "         _attempt()" },
    ],
  },
  {
    file: "tests/test_writer.py", badge: null, symbol: "test_write_retries_then_fails()",
    add: 24, del: 2, risk: null,
    note: "new test · mocks transient 503 → asserts 3 attempts",
    hunk: [
      { t: "add", s: "def test_write_retries_then_fails(mock_conn):" },
      { t: "add", s: "    mock_conn.copy.side_effect = [Err503, Err503, Err503]" },
      { t: "add", s: "    with pytest.raises(SnowflakeWriteError):" },
      { t: "add", s: "        writer.write_df(df, 'scores')" },
      { t: "add", s: "    assert mock_conn.copy.call_count == 3" },
    ],
  },
];

const episodes = [
  {
    title: "Add retry with backoff to Snowflake writer",
    prompt: "the snowflake writer keeps dying on transient 503s — add retries with backoff",
    proposed: 5, applied: 3, revised: 1, rejected: 1,
    add: 68, del: 9,
    verified: { ran: "pytest tests/test_writer.py", result: "4 passed" },
    edits: [
      {
        file: "dataio/retry.py", symbol: "with_backoff()", state: "applied",
        hunk: [
          { t: "add", s: "def with_backoff(retries=3, base=2.0):" },
          { t: "add", s: "    def deco(fn): ..." },
          { t: "add", s: "    return deco" },
        ],
      },
      {
        file: "dataio/snowflake/writer.py", symbol: "write_df()", state: "applied",
        hunk: [
          { t: "del", s: "         self._copy_into(df, table)" },
          { t: "add", s: "         @with_backoff(retries=cfg.write_retries)" },
          { t: "add", s: "         def _attempt(): self._copy_into(df, table)" },
          { t: "add", s: "         _attempt()" },
        ],
      },
      {
        file: "dataio/config.py", symbol: "DEFAULTS", state: "applied",
        hunk: [
          { t: "del", s: '     "write_timeout_s": 60,' },
          { t: "add", s: '     "write_timeout_s": 120,' },
          { t: "add", s: '     "write_retries": 3,' },
        ],
      },
      {
        file: "dataio/snowflake/writer.py", symbol: "write_df()", state: "revised",
        detail: "1st proposal retried inside the cursor loop — you asked for retry at call level; 2nd proposal applied",
        proposedHunk: [
          { t: "add", s: "         for row_batch in chunks(df):" },
          { t: "add", s: "             for attempt in range(3):" },
          { t: "add", s: "                 self._copy_batch(row_batch)" },
        ],
        appliedHunk: [
          { t: "add", s: "         @with_backoff(retries=cfg.write_retries)" },
          { t: "add", s: "         def _attempt(): self._copy_into(df, table)" },
          { t: "add", s: "         _attempt()" },
        ],
      },
      {
        file: "dataio/base.py", symbol: "IOBase.write()", state: "rejected",
        detail: "proposed adding retries to the shared base class — rejected: too broad, pandas path doesn't want it",
        proposedHunk: [
          { t: "ctx", s: " class IOBase:" },
          { t: "add", s: "     @with_backoff()" },
          { t: "ctx", s: "     def write(self, df, dest):" },
        ],
      },
    ],
  },
  {
    title: "Fix flaky assertion in test_writer",
    prompt: "test_write_chunks is flaky, look at it",
    proposed: 1, applied: 1, revised: 0, rejected: 0,
    add: 6, del: 4,
    verified: { ran: "pytest -k chunks ×20", result: "20 passed" },
    edits: [
      {
        file: "tests/test_writer.py", symbol: "test_write_chunks()", state: "applied",
        hunk: [
          { t: "del", s: "     assert time.time() - t0 < 0.5" },
          { t: "add", s: "     assert mock_conn.copy.call_count == n_chunks" },
        ],
      },
    ],
  },
];

// ── atoms ────────────────────────────────────────────────────────────
const GLYPH = {
  applied: { ch: "✓", c: C.green },
  revised: { ch: "✎", c: C.violet },
  rejected: { ch: "✗", c: C.red },
};

const Glyph = ({ state }) => (
  <span style={{ color: GLYPH[state].c, width: 16, display: "inline-block" }}>
    {GLYPH[state].ch}
  </span>
);

const Stat = ({ add, del }) => (
  <span style={{ ...mono, fontSize: 11, whiteSpace: "nowrap" }}>
    <span style={{ color: C.green }}>+{add}</span>{" "}
    <span style={{ color: C.red }}>−{del}</span>
  </span>
);

const Chip = ({ children, color }) => (
  <span style={{
    ...mono, fontSize: 10, color, border: `1px solid ${color}55`,
    borderRadius: 3, padding: "1px 6px", whiteSpace: "nowrap",
  }}>{children}</span>
);

// risk chip that explains itself on tap
const RiskChip = ({ risk }) => {
  const [open, setOpen] = useState(false);
  if (!risk) return null;
  return (
    <span style={{ display: "inline-block" }}>
      <span
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        style={{
          ...mono, fontSize: 10, color: C.amber, border: `1px solid ${C.amber}55`,
          borderRadius: 3, padding: "1px 6px", whiteSpace: "nowrap", cursor: "pointer",
          background: open ? C.amberDim : "transparent",
        }}>
        {risk} {open ? "▾" : "?"}
      </span>
      {open && (
        <span style={{
          ...mono, display: "block", fontSize: 10.5, color: C.dim,
          margin: "5px 0 2px", paddingLeft: 8, borderLeft: `2px solid ${C.amber}55`,
          maxWidth: 480,
        }}>
          {RISK_INFO[risk]}
        </span>
      )}
    </span>
  );
};

const DeltaStrip = ({ proposed, applied, revised, rejected }) => {
  const seg = (n, color) => n > 0 && (
    <div style={{ flex: n, background: color, minWidth: 8 }} />
  );
  return (
    <div>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", gap: 2 }}>
        {seg(applied, C.green)}{seg(revised, C.violet)}{seg(rejected, C.red)}
      </div>
      <div style={{ ...mono, fontSize: 10, color: C.dim, marginTop: 4 }}>
        {proposed} proposed → <span style={{ color: C.green }}>{applied} applied</span>
        {revised > 0 && <> · <span style={{ color: C.violet }}>{revised} revised</span></>}
        {rejected > 0 && <> · <span style={{ color: C.red }}>{rejected} rejected</span></>}
      </div>
    </div>
  );
};

const DiffHunk = ({ hunk, frame }) => (
  <pre style={{
    ...mono, fontSize: 11, lineHeight: 1.55, margin: 0, padding: "8px 10px",
    background: C.bg, border: `1px solid ${frame || C.line}`, borderRadius: 4,
    overflowX: "auto",
  }}>
    {hunk.map((l, i) => (
      <div key={i} style={{
        color: l.t === "add" ? C.green : l.t === "del" ? C.red : C.faint,
        background: l.t === "add" ? C.greenDim : l.t === "del" ? C.redDim : "transparent",
      }}>
        {l.t === "add" ? "+" : l.t === "del" ? "−" : " "}{l.s}
      </div>
    ))}
  </pre>
);

const HunkLabel = ({ color, children }) => (
  <div style={{ ...mono, fontSize: 9.5, color, letterSpacing: 1.2, margin: "8px 0 4px" }}>
    {children}
  </div>
);

// third drill level: an edit's actual diff, shaped by its fate
const EditDetail = ({ edit }) => {
  if (edit.state === "revised") return (
    <div style={{ marginLeft: 16, marginTop: 4 }}>
      <HunkLabel color={C.violet}>PROPOSED — SUPERSEDED</HunkLabel>
      <DiffHunk hunk={edit.proposedHunk} frame={`${C.violet}44`} />
      <HunkLabel color={C.green}>APPLIED</HunkLabel>
      <DiffHunk hunk={edit.appliedHunk} frame={`${C.green}44`} />
    </div>
  );
  if (edit.state === "rejected") return (
    <div style={{ marginLeft: 16, marginTop: 4 }}>
      <HunkLabel color={C.red}>PROPOSED — NEVER APPLIED</HunkLabel>
      <DiffHunk hunk={edit.proposedHunk} frame={`${C.red}44`} />
    </div>
  );
  return (
    <div style={{ marginLeft: 16, marginTop: 4 }}>
      <HunkLabel color={C.green}>APPLIED</HunkLabel>
      <DiffHunk hunk={edit.hunk} frame={`${C.green}33`} />
    </div>
  );
};

// ── LIVE view (pre-approval) ─────────────────────────────────────────
const LiveView = () => {
  const [open, setOpen] = useState(null);
  return (
    <div>
      <div style={{
        display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center",
        ...mono, fontSize: 11, color: C.dim, padding: "10px 2px",
      }}>
        <span><span style={{ color: C.amber }}>1</span> awaiting you</span>
        <span><span style={{ color: C.green }}>3</span> applied</span>
        <span>4 files · 3 symbols</span>
        <Stat add={80} del={9} />
      </div>

      {/* pending approval — always fully open */}
      <div style={{
        border: `1px solid ${C.amber}`, borderRadius: 6, background: C.panelHi,
        boxShadow: `0 0 0 3px ${C.amberDim}`, marginBottom: 16,
      }}>
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "8px 12px", borderBottom: `1px solid ${C.line}`, flexWrap: "wrap", gap: 6,
        }}>
          <span style={{ ...mono, fontSize: 11, color: C.amber, letterSpacing: 1 }}>
            ● AWAITING APPROVAL
          </span>
          <span style={{ ...mono, fontSize: 10, color: C.dim }}>waiting 0:42</span>
        </div>
        <div style={{ padding: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 6, marginBottom: 4 }}>
            <span style={{ ...mono, fontSize: 12, color: C.text }}>
              {pendingEdit.file} <span style={{ color: C.faint }}>›</span>{" "}
              <span style={{ color: C.cyan }}>{pendingEdit.symbol}</span>
            </span>
            <Stat add={pendingEdit.add} del={pendingEdit.del} />
          </div>
          <div style={{ margin: "6px 0 10px", display: "flex", gap: 6, flexWrap: "wrap", alignItems: "flex-start" }}>
            <RiskChip risk={pendingEdit.risk} />
            <Chip color={C.faint}>imported by 7 modules · v2</Chip>
          </div>
          <DiffHunk hunk={pendingEdit.hunk} />
          <div style={{ ...mono, fontSize: 10, color: C.faint, marginTop: 8 }}>
            approve / reject in Claude Code — lens is read-only
          </div>
        </div>
      </div>

      <div style={{ ...mono, fontSize: 10, color: C.faint, letterSpacing: 1.5, margin: "0 2px 6px" }}>
        APPLIED THIS SESSION
      </div>
      {appliedEdits.map((e, i) => (
        <div key={i}
          onClick={() => setOpen(open === i ? null : i)}
          style={{
            border: `1px solid ${C.line}`, borderRadius: 5, background: C.panel,
            padding: "9px 12px", marginBottom: 6, cursor: "pointer",
          }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <span style={{ ...mono, fontSize: 12, color: C.text }}>
              <span style={{ color: C.green, width: 16, display: "inline-block" }}>✓</span>
              {e.file}
              {e.badge && <> <Chip color={C.cyan}>{e.badge}</Chip></>}
              {e.risk && <> <RiskChip risk={e.risk} /></>}
            </span>
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Stat add={e.add} del={e.del} />
              <span style={{ ...mono, fontSize: 10, color: C.faint }}>{open === i ? "▾" : "▸"}</span>
            </span>
          </div>
          {open === i && (
            <div onClick={(ev) => ev.stopPropagation()}>
              <div style={{ ...mono, fontSize: 11, color: C.dim, marginTop: 6, paddingLeft: 16 }}>
                <span style={{ color: C.cyan }}>{e.symbol}</span> — {e.note}
              </div>
              <div style={{ marginTop: 2 }}>
                <EditDetail edit={{ state: "applied", hunk: e.hunk }} />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

// ── SESSION view (post-edit) ─────────────────────────────────────────
const SessionView = () => {
  const [openEp, setOpenEp] = useState(0);
  const [openEdit, setOpenEdit] = useState("0-3"); // revised edit starts open to show the payoff
  return (
    <div>
      <div style={{
        display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center",
        ...mono, fontSize: 11, color: C.dim, padding: "10px 2px",
      }}>
        <span>2 episodes</span>
        <span>4 files</span>
        <Stat add={74} del={13} />
        <span style={{ color: C.green }}>tests ✓</span>
      </div>

      {episodes.map((ep, i) => (
        <div key={i} style={{
          border: `1px solid ${C.line}`, borderRadius: 6, background: C.panel, marginBottom: 12,
        }}>
          <div onClick={() => setOpenEp(openEp === i ? null : i)}
            style={{ padding: "11px 13px", cursor: "pointer" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 13, color: C.text, fontWeight: 600 }}>{ep.title}</span>
              <Stat add={ep.add} del={ep.del} />
            </div>
            <div style={{ ...mono, fontSize: 10, color: C.faint, margin: "3px 0 9px" }}>
              you: “{ep.prompt}”
            </div>
            <DeltaStrip {...ep} />
          </div>

          {openEp === i && (
            <div style={{ borderTop: `1px solid ${C.line}`, padding: "10px 13px" }}>
              {ep.edits.map((ed, j) => {
                const k = `${i}-${j}`;
                const isOpen = openEdit === k;
                return (
                  <div key={j} style={{ marginBottom: 8 }}>
                    <div
                      onClick={() => setOpenEdit(isOpen ? null : k)}
                      style={{ cursor: "pointer" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                        <span style={{ ...mono, fontSize: 12, color: C.text }}>
                          <Glyph state={ed.state} />
                          {ed.file} <span style={{ color: C.faint }}>›</span>{" "}
                          <span style={{ color: C.cyan }}>{ed.symbol}</span>
                        </span>
                        <span style={{ ...mono, fontSize: 10, color: C.faint }}>{isOpen ? "▾" : "▸"}</span>
                      </div>
                      {ed.detail && (
                        <div style={{
                          ...mono, fontSize: 10.5, color: C.dim, margin: "3px 0 0 16px",
                          paddingLeft: 8,
                          borderLeft: `2px solid ${ed.state === "rejected" ? C.red : C.violet}55`,
                        }}>
                          {ed.detail}
                        </div>
                      )}
                    </div>
                    {isOpen && <EditDetail edit={ed} />}
                  </div>
                );
              })}
              <div style={{
                ...mono, fontSize: 10.5, color: C.green, marginTop: 10,
                background: C.greenDim, border: `1px solid ${C.green}33`,
                borderRadius: 4, padding: "5px 9px",
              }}>
                ✓ verified — ran {ep.verified.ran} → {ep.verified.result}
              </div>
            </div>
          )}
        </div>
      ))}
      <div style={{ ...mono, fontSize: 10, color: C.faint, textAlign: "center", padding: 6 }}>
        rendered from session JSONL + git — no AI in this summary
      </div>
    </div>
  );
};

// ── shell ────────────────────────────────────────────────────────────
export default function ChangeLens() {
  const [mode, setMode] = useState("session");
  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "18px 14px" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@500;700&display=swap');`}</style>
      <div style={{ maxWidth: 620, margin: "0 auto" }}>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
          <div>
            <span style={{
              fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 20,
              color: C.text, letterSpacing: 0.5,
            }}>
              lens<span style={{ color: C.cyan }}>_</span>
            </span>
            <span style={{ ...mono, fontSize: 10, color: C.faint, marginLeft: 10 }}>
              dataio · session 9f2c · 14 min
            </span>
          </div>

          <div style={{ display: "flex", border: `1px solid ${C.line}`, borderRadius: 5, overflow: "hidden" }}>
            {[["live", "LIVE"], ["session", "SESSION"]].map(([k, label]) => (
              <button key={k} onClick={() => setMode(k)} style={{
                ...mono, fontSize: 11, letterSpacing: 1, padding: "5px 14px",
                background: mode === k ? C.panelHi : "transparent",
                color: mode === k ? (k === "live" ? C.amber : C.green) : C.faint,
                border: "none", cursor: "pointer",
                borderBottom: mode === k ? `2px solid ${k === "live" ? C.amber : C.green}` : "2px solid transparent",
              }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ ...mono, fontSize: 10.5, color: C.dim, margin: "6px 0 8px" }}>
          {mode === "live"
            ? "what Claude wants to change — structural view of queued + applied edits"
            : "what Claude actually changed — proposed vs applied, by episode"}
        </div>

        {mode === "live" ? <LiveView /> : <SessionView />}
      </div>
    </div>
  );
}
