"use client";
import Link from "next/link";
import { ArrowUpRight, Plus } from "lucide-react";
import { useApp } from "../components/AppProvider";
import { ClubOverview } from "../components/ClubOverview";
import { ChatPanel } from "../components/ChatPanel";
export default function Home() {
  const app = useApp();
  const prompts = [
    "เล่าประวัติของ " + app.team.name,
    app.team.name + " แข่งนัดล่าสุดเป็นอย่างไร?",
    "อันดับพรีเมียร์ลีกตอนนี้เป็นอย่างไร?",
    "สรุปผลพรีเมียร์ลีกในสัปดาห์ล่าสุด",
    "วันนี้อากาศเป็นอย่างไร?",
  ];
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">{app.team.hero}</span>
          <h1>{app.team.name}</h1>
          <p>ทุกเรื่องของทีมที่คุณรัก</p>
          <span className="badge">CLUB COMPANION · {app.team.shortName}</span>
        </div>
      </section>
      <div className="dashboard-grid">
        <section className="panel main-chat">
          <header className="panel-heading">
            <div>
              <span className="eyebrow">FOOTBALL INTELLIGENCE</span>
              <h2>Ask PitchSide</h2>
            </div>
            <button onClick={app.newChat}>
              <Plus size={16} />
              แชทใหม่
            </button>
          </header>
          <ChatPanel />
        </section>
        <aside className="dashboard-side">
          <ClubOverview />
          <section className="panel">
            <span className="eyebrow">START A CONVERSATION</span>
            <h2>เริ่มจากคำถามนี้</h2>
            <div className="prompt-list">
              {prompts.map((prompt, index) => (
                <button key={prompt} onClick={() => app.ask(prompt)}>
                  <small>
                    {
                      [
                        "ประวัติทีม",
                        "ผลการแข่งขัน",
                        "ตารางคะแนน",
                        "สรุปสัปดาห์",
                        "ลองคำถามนอกขอบเขต",
                      ][index]
                    }
                  </small>
                  <span>{prompt}</span>
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          </section>
          <section className="panel companion-card">
            <span className="eyebrow">YOUR MATCHDAY COMPANION</span>
            <h2>เพื่อนเชียร์บอลของคุณ</h2>
            <p>ลากมาสคอสไปตรงที่ชอบ แล้วแตะเพื่อคุยได้จากทุกหน้า</p>
            <Link className="text-link" href="/football/fixtures">
              ดูโปรแกรมการแข่งขัน <ArrowUpRight size={16} />
            </Link>
          </section>
        </aside>
      </div>
    </>
  );
}
