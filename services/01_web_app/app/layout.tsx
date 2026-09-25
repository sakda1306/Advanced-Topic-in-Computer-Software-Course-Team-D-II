import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PitchSide | Football Assistant",
  description: "ผู้ช่วยฟุตบอลพรีเมียร์ลีก พร้อมคำตอบและแหล่งอ้างอิง",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}
