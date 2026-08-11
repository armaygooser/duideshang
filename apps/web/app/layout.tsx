import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "对得上 DuiDeShang", description: "广告制作需求澄清与可解释报价助手" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-CN"><body>{children}</body></html>; }
