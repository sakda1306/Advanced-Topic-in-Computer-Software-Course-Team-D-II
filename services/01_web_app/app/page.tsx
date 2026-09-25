"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { MascotDock } from "../components/MascotDock";
import { TeamKey, teamFromId, teams } from "../lib/teams";

export type Source = {
  ref: number;
  title: string;
  origin: string | null;
  url: string | null;
};

export type ChatEntry = {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  sources?: Source[];
  dataAsOf?: string | null;
};

type User = {
  id: string;
  display_name: string;
  favorite_team_id: number | null;
};

type ChatResult = {
  session_id: string;
  message_id: string;
  answer: string;
  sources: Source[];
  data_as_of: string | null;
};

function problemDetail(value: unknown, fallback: string): string {
  if (value && typeof value === "object" && "detail" in value) {
    const detail = (value as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export default function Home() {
  const [selectedKey, setSelectedKey] = useState<TeamKey>("manchester-united");
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [entries, setEntries] = useState<Partial<Record<TeamKey, ChatEntry[]>>>({});
  const [pendingTeam, setPendingTeam] = useState<TeamKey | null>(null);
  const [openSignal, setOpenSignal] = useState(0);
  const [notice, setNotice] = useState("");
  const sessions = useRef<Partial<Record<TeamKey, string>>>({});

  const team = useMemo(
    () => teams.find((item) => item.key === selectedKey) ?? teams[0],
    [selectedKey],
  );

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/auth/me", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const data = (await response.json()) as { user: User };
        if (cancelled) return;
        setUser(data.user);
        const favorite = teamFromId(data.user.favorite_team_id);
        if (favorite) setSelectedKey(favorite.key);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setAuthChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function login(username: string, password: string): Promise<string | null> {
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data: unknown = await response.json();
      if (!response.ok) return problemDetail(data, "เข้าสู่ระบบไม่สำเร็จ");
      const loggedIn = (data as { user: User }).user;
      setUser(loggedIn);
      const favorite = teamFromId(loggedIn.favorite_team_id);
      if (favorite) setSelectedKey(favorite.key);
      setNotice("");
      return null;
    } catch {
      return "เชื่อมต่อระบบเข้าสู่ระบบไม่ได้";
    }
  }

  async function changeTeam(key: TeamKey) {
    const next = teams.find((item) => item.key === key);
    if (!next) return;
    setSelectedKey(key);
    setNotice("");
    if (!user) return;
    try {
      const response = await fetch("/api/me/preferences", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ favorite_team_id: next.teamId }),
      });
      if (!response.ok) {
        const data: unknown = await response.json().catch(() => null);
        setNotice(problemDetail(data, "บันทึกทีมที่เชียร์ไม่สำเร็จ"));
        if (response.status === 401) setUser(null);
      } else {
        setUser({ ...user, favorite_team_id: next.teamId });
      }
    } catch {
      setNotice("แสดงธีมใหม่แล้ว แต่ยังบันทึกทีมที่เชียร์ไม่ได้");
    }
  }

  async function sendQuestion(question: string): Promise<boolean> {
    const message = question.trim();
    if (!message || message.length > 2000 || pendingTeam) return false;
    const key = selectedKey;
    setEntries((current) => ({
      ...current,
      [key]: [
        ...(current[key] ?? []),
        { id: crypto.randomUUID(), role: "user", content: message },
      ],
    }));
    setPendingTeam(key);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: sessions.current[key] ?? null, message }),
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        if (response.status === 401) setUser(null);
        throw new Error(problemDetail(data, "ส่งคำถามไม่สำเร็จ"));
      }
      const answer = data as ChatResult;
      sessions.current[key] = answer.session_id;
      setEntries((current) => ({
        ...current,
        [key]: [
          ...(current[key] ?? []),
          {
            id: answer.message_id,
            role: "assistant",
            content: answer.answer,
            sources: answer.sources,
            dataAsOf: answer.data_as_of,
          },
        ],
      }));
    } catch (error) {
      setEntries((current) => ({
        ...current,
        [key]: [
          ...(current[key] ?? []),
          {
            id: crypto.randomUUID(),
            role: "error",
            content: error instanceof Error ? error.message : "เกิดข้อผิดพลาด",
          },
        ],
      }));
    } finally {
      setPendingTeam(null);
    }
    return true;
  }

  return (
    <main
      className="site-shell"
      style={
        {
          "--club": team.color,
          "--club-bright": team.colorBright,
          "--club-glow": team.glow,
        } as React.CSSProperties
      }
    >
      <div className="stadium-light stadium-light-left" aria-hidden="true" />
      <div className="stadium-light stadium-light-right" aria-hidden="true" />
      <aside className="site-sidebar">
        <div className="wordmark"><span className="wordmark-symbol">P</span><span>PitchSide<small>FOOTBALL ASSISTANT</small></span></div>
        <p className="sidebar-eyebrow">YOUR FOOTBALL WORLD</p>
        <nav aria-label="เมนูหลัก">
          <a className="sidebar-link active" href="#assistant">แชทฟุตบอล</a>
          <a className="sidebar-link" href="#match">ผลการแข่งขัน</a>
          <a className="sidebar-link" href="#standings">ตารางคะแนน</a>
          <a className="sidebar-link" href="#reports">รายงานประจำสัปดาห์</a>
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-tip">
          <span>MEET YOUR MASCOT</span>
          <p>แตะตัวแพนด้าเพื่อถามเรื่องฟุตบอล หรือลากไปไว้ตรงที่ชอบ</p>
        </div>
        <div className="sidebar-account">{user?.display_name ?? "ผู้เยี่ยมชม"}<small>{user ? "พร้อมคุยเรื่องพรีเมียร์ลีก" : "เข้าสู่ระบบเพื่อถามคำถาม"}</small></div>
      </aside>

      <div className="site-content">
        <header className="topbar">
          <div className="season">PREMIER LEAGUE <span>2026 / 27</span></div>
          <div className="club-switcher" role="group" aria-label="เลือกทีมที่เชียร์">
            {teams.map((item) => (
              <button
                key={item.key}
                type="button"
                className={"club-option" + (selectedKey === item.key ? " selected" : "")}
                aria-pressed={selectedKey === item.key}
                onClick={() => void changeTeam(item.key)}
              >
                <span className="club-monogram" aria-hidden="true">{item.initials}</span>
                <span>{item.shortName}</span>
                {selectedKey === item.key && <span className="selected-check" aria-hidden="true">✓</span>}
              </button>
            ))}
          </div>
        </header>

        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <div className="hero-kicker">YOUR CLUB. YOUR WORLD.</div>
            <h1 id="hero-title">{team.name}</h1>
            <p>{team.hero}</p>
            <span className="hero-caption">ทุกเรื่องของทีมที่คุณรัก ในพื้นที่เดียว</span>
          </div>
          <div className="pitch-lines" aria-hidden="true"><span /></div>
          <div className="hero-orb" aria-hidden="true">{team.initials}</div>
        </section>

        {notice && <div className="site-notice" role="status">{notice}</div>}

        <div className="dashboard-grid">
          <section className="feature-card assistant-card" id="assistant">
            <div className="card-eyebrow">FOOTBALL INTELLIGENCE</div>
            <h2>Ask PitchSide</h2>
            <p>มาสคอสพร้อมช่วยค้นคำตอบจากข้อมูลฟุตบอลและบอกแหล่งที่มา</p>
            <div className="assistant-prompts">
              {[
                "ทีมนี้แข่งนัดล่าสุดเป็นอย่างไร?",
                "อันดับพรีเมียร์ลีกตอนนี้เป็นอย่างไร?",
                "สรุปข่าวและผลแข่งในสัปดาห์นี้",
              ].map((prompt) => (
                <button key={prompt} type="button" onClick={() => { setOpenSignal((n) => n + 1); }}>{prompt}</button>
              ))}
            </div>
            <div className="assistant-action">
              <button type="button" onClick={() => setOpenSignal((n) => n + 1)}>
                เปิดแชทกับมาสคอส <span aria-hidden="true">↗</span>
              </button>
              <span>แชทใช้บัญชีผู้ใช้ของระบบ</span>
            </div>
          </section>
          <div className="dashboard-side">
            <section className="feature-card match-card" id="match">
              <div className="card-eyebrow">YOUR CLUB</div>
              <h2>ติดตามทีมโปรด</h2>
              <div className="match-emblem">{team.initials}</div>
              <p>{team.name}</p>
              <span>เลือกทีมด้านบนเพื่อเปลี่ยนบรรยากาศเว็บและมาสคอส</span>
            </section>
            <section className="feature-card info-card" id="standings">
              <div className="card-eyebrow">CLUB COMPANION</div>
              <h2>เพื่อนเชียร์บอลของคุณ</h2>
              <p>{team.mascot ? "มาสคอสประจำทีมพร้อมขยับและตอบคำถาม" : "มาสคอสของ Liverpool กำลังจะมาเร็ว ๆ นี้"}</p>
              <div className="info-line"><span>ทีมที่เลือก</span><strong>{team.shortName}</strong></div>
              <div className="info-line"><span>มาสคอส</span><strong>{team.mascot ? "พร้อมใช้งาน" : "เร็ว ๆ นี้"}</strong></div>
            </section>
          </div>
        </div>
        <footer id="reports">คำตอบจากระบบอาจใช้เวลาสักครู่ · ตรวจสอบแหล่งอ้างอิงและเวลาข้อมูลทุกครั้ง</footer>
      </div>

      <MascotDock
        team={team}
        entries={entries[selectedKey] ?? []}
        pending={pendingTeam === selectedKey}
        busy={pendingTeam !== null}
        user={user}
        authChecked={authChecked}
        openSignal={openSignal}
        onSend={sendQuestion}
        onLogin={login}
      />
    </main>
  );
}
