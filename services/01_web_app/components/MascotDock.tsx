"use client";

import { FormEvent, PointerEvent, useEffect, useRef, useState } from "react";
import type { ChatEntry } from "../app/page";
import type { Team } from "../lib/teams";

type Props = {
  team: Team;
  entries: ChatEntry[];
  pending: boolean;
  busy: boolean;
  user: { display_name: string } | null;
  authChecked: boolean;
  openSignal: number;
  onSend: (question: string) => Promise<boolean>;
  onLogin: (username: string, password: string) => Promise<string | null>;
};

const CELL_W = 192;
const CELL_H = 208;
const SCALE = 0.75;
const PET_W = CELL_W * SCALE;
const PET_H = CELL_H * SCALE;

function clampPosition(x: number, y: number) {
  return {
    x: Math.max(8, Math.min(x, window.innerWidth - PET_W - 8)),
    y: Math.max(8, Math.min(y, window.innerHeight - PET_H - 8)),
  };
}

export function MascotDock({ team, entries, pending, busy, user, authChecked, openSignal, onSend, onLogin }: Props) {
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [open, setOpen] = useState(false);
  const [frame, setFrame] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [direction, setDirection] = useState<"left" | "right">("right");
  const [question, setQuestion] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [waveUntil, setWaveUntil] = useState(0);
  const drag = useRef<{ startX: number; startY: number; originalX: number; originalY: number; moved: boolean } | null>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("pitchside-mascot-position");
    try {
      const point = saved ? JSON.parse(saved) as { x: number; y: number } : null;
      setPosition(clampPosition(point?.x ?? window.innerWidth - PET_W - 34, point?.y ?? window.innerHeight - PET_H - 38));
    } catch {
      setPosition(clampPosition(window.innerWidth - PET_W - 34, window.innerHeight - PET_H - 38));
    }
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotion = () => setReducedMotion(media.matches);
    updateMotion();
    media.addEventListener("change", updateMotion);
    const onResize = () => setPosition((current) => current && clampPosition(current.x, current.y));
    window.addEventListener("resize", onResize);
    return () => {
      media.removeEventListener("change", updateMotion);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  useEffect(() => {
    if (openSignal > 0) {
      setOpen(true);
      setWaveUntil(Date.now() + 1000);
    }
  }, [openSignal]);

  useEffect(() => {
    if (reducedMotion || !team.mascot) return;
    const timer = window.setInterval(() => setFrame((current) => (current + 1) % 8), pending ? 115 : 170);
    return () => window.clearInterval(timer);
  }, [pending, reducedMotion, team.mascot]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: reducedMotion ? "instant" : "smooth", block: "end" });
  }, [entries, pending, open, reducedMotion]);

  function pointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (!position) return;
    drag.current = { startX: event.clientX, startY: event.clientY, originalX: position.x, originalY: position.y, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function pointerMove(event: PointerEvent<HTMLButtonElement>) {
    if (!drag.current) return;
    const dx = event.clientX - drag.current.startX;
    const dy = event.clientY - drag.current.startY;
    if (Math.abs(dx) + Math.abs(dy) > 5) drag.current.moved = true;
    if (!drag.current.moved) return;
    setDragging(true);
    setDirection(dx < 0 ? "left" : "right");
    setPosition(clampPosition(drag.current.originalX + dx, drag.current.originalY + dy));
  }

  function pointerUp(event: PointerEvent<HTMLButtonElement>) {
    if (!drag.current) return;
    const moved = drag.current.moved;
    drag.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (moved) {
      setPosition((current) => {
        if (current) localStorage.setItem("pitchside-mascot-position", JSON.stringify(current));
        return current;
      });
    } else {
      setOpen((value) => !value);
      setWaveUntil(Date.now() + 1000);
    }
  }

  function keyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    const steps: Record<string, [number, number]> = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] };
    const step = steps[event.key];
    if (!step || !position) return;
    event.preventDefault();
    const next = clampPosition(position.x + step[0], position.y + step[1]);
    setPosition(next);
    localStorage.setItem("pitchside-mascot-position", JSON.stringify(next));
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    const sent = await onSend(question);
    if (sent) setQuestion("");
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoggingIn(true);
    const error = await onLogin(username, password);
    setLoginError(error ?? "");
    if (!error) setPassword("");
    setLoggingIn(false);
  }

  const row = dragging ? (direction === "right" ? 1 : 2) : pending ? 7 : waveUntil > Date.now() ? 3 : 0;
  const panelWidth = Math.min(380, Math.max(280, typeof window === "undefined" ? 380 : window.innerWidth - 24));
  const left = position ? Math.max(12, Math.min(position.x + PET_W / 2 - panelWidth / 2, window.innerWidth - panelWidth - 12)) : 12;
  const viewportHeight = typeof window === "undefined" ? 800 : window.innerHeight;
  const panelHeight = Math.min(505, viewportHeight - 24);
  const panelTop = position ? Math.max(12, Math.min(position.y >= panelHeight + 20 ? position.y - panelHeight - 10 : position.y + PET_H + 10, viewportHeight - panelHeight - 12)) : 12;

  return (
    <div className="mascot-layer">
      {open && position && (
        <section className="mascot-chat" aria-label="แชทกับมาสคอส" style={{ left, width: panelWidth, top: panelTop, height: panelHeight }}>
          <div className="chat-heading">
            <div><span className="chat-online" /><strong>{team.shortName} Companion</strong><small>{team.mascot ? "เพื่อนคุยฟุตบอลประจำทีม" : "แชทฟุตบอล · มาสคอสกำลังมา"}</small></div>
            <button type="button" aria-label="ปิดแชท" onClick={() => setOpen(false)}>×</button>
          </div>
          {!authChecked ? <p className="chat-state">กำลังตรวจสอบบัญชี…</p> : !user ? (
            <form className="chat-login" onSubmit={(event) => void submitLogin(event)}>
              <p>เข้าสู่ระบบเพื่อคุยกับมาสคอส</p>
              <label>ชื่อผู้ใช้<input required autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
              <label>รหัสผ่าน<input required type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
              {loginError && <span className="form-error" role="alert">{loginError}</span>}
              <button type="submit" disabled={loggingIn}>{loggingIn ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}</button>
            </form>
          ) : (
            <>
              <div className="chat-messages" role="log" aria-live="polite" aria-relevant="additions text">
                {entries.length === 0 && <div className="chat-welcome"><span>✦</span><strong>สวัสดี {user.display_name}</strong><p>ถามเรื่องพรีเมียร์ลีก ผลการแข่งขัน หรือตารางคะแนนได้เลย</p></div>}
                {entries.map((entry) => (
                  <div key={entry.id} className={"chat-message " + entry.role}>
                    <p>{entry.content}</p>
                    {entry.sources && entry.sources.length > 0 && <div className="chat-sources">แหล่งข้อมูล: {entry.sources.map((source, index) => <span key={source.ref}>{index > 0 ? " · " : ""}{source.url?.startsWith("https://") ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a> : source.title}</span>)}</div>}
                    {entry.dataAsOf && <small>ข้อมูล ณ {entry.dataAsOf}</small>}
                  </div>
                ))}
                {pending && <div className="chat-message assistant thinking">กำลังหาคำตอบ<span className="thinking-dots">…</span></div>}
                <div ref={messagesEnd} />
              </div>
              <form className="chat-compose" onSubmit={(event) => void submitQuestion(event)}>
                <label className="sr-only" htmlFor="mascot-question">ถามมาสคอส</label>
                <textarea id="mascot-question" rows={2} maxLength={2000} placeholder="ถามเรื่องฟุตบอลได้เลย…" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} />
                <button type="submit" disabled={!question.trim() || busy} aria-label="ส่งคำถาม">➜</button>
              </form>
            </>
          )}
        </section>
      )}
      {position && <button type="button" className={"mascot-pet" + (dragging ? " dragging" : "")} style={{ left: position.x, top: position.y }} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={() => { drag.current = null; setDragging(false); }} onKeyDown={keyDown} aria-label={team.mascot ? "มาสคอส " + team.name + " กดเพื่อเปิดแชท หรือลากเพื่อย้ายตำแหน่ง" : "เปิดแชทฟุตบอล มาสคอส Liverpool กำลังมา"} aria-expanded={open}>
        {team.mascot ? <span className="mascot-sprite" style={{ backgroundImage: "url(" + team.mascot + ")", backgroundPosition: (-frame * CELL_W * SCALE) + "px " + (-row * CELL_H * SCALE) + "px" }} aria-hidden="true" /> : <span className="mascot-placeholder" aria-hidden="true"><span>✦</span><small>SOON</small></span>}
        <span className="mascot-hint">{team.mascot ? "ถามฉันได้เลย" : "แชทได้เลย"}</span>
      </button>}
    </div>
  );
}
