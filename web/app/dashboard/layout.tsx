"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DataProvider } from "@/lib/data-context";
import { useAuth } from "@/lib/auth";
import { Trophy, Activity, Gem, Gift, User, ChevronLeft, ChevronRight, LogOut, Shield } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "积分排行", icon: Trophy },
  { href: "/dashboard/activity", label: "活跃度", icon: Activity },
  { href: "/dashboard/dragons", label: "龙珠榜", icon: Gem },
  { href: "/dashboard/rewards", label: "积分商城", icon: Gift },
  { href: "/dashboard/me", label: "个人中心", icon: User },
];

const ADMIN_ITEMS = [
  { href: "/dashboard/admin", label: "管理", icon: Shield },
];

function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    await logout();
  };

  return (
    <aside className={`relative flex flex-col border-r border-[rgba(167,139,250,0.07)] bg-[#0b0810] transition-all duration-300 ease-in-out shrink-0 ${collapsed ? "w-[56px]" : "w-[200px]"}`}>
      <div className="absolute inset-0 pointer-events-none opacity-30" style={{ background: "radial-gradient(ellipse 60% 100% at 50% 0%, rgba(167,139,250,0.05), transparent 70%)" }} />
      <div className="relative flex items-center gap-2 px-3.5 h-12 border-b border-[rgba(167,139,250,0.07)]">
        <img src="/logo.jpg" alt="前进四" className="w-6 h-6 rounded-md object-cover shrink-0" />
        {!collapsed && <span className="text-sm font-semibold tracking-tight text-[#eae4f0]">前进四</span>}
      </div>
      <nav className="relative flex-1 px-1.5 py-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} prefetch={true}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive ? "bg-[rgba(167,139,250,0.1)] text-[#eae4f0]" : "text-[#7e7594] hover:text-[#c4bdd4] hover:bg-[rgba(167,139,250,0.04)]"}`}>
              <item.icon className="w-3.5 h-3.5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
        {!collapsed && <div className="mx-1.5 my-1 border-t border-[rgba(167,139,250,0.05)]" />}
        {ADMIN_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} prefetch={true}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive ? "bg-[rgba(167,139,250,0.1)] text-[#eae4f0]" : "text-[#5c5470] hover:text-[#a78bfa] hover:bg-[rgba(167,139,250,0.04)]"}`}>
              <item.icon className="w-3.5 h-3.5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="relative px-1.5 py-2 border-t border-[rgba(167,139,250,0.07)] flex flex-col gap-0.5">
        <button onClick={() => setCollapsed(!collapsed)} className="flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-[#5c5470] hover:text-[#7e7594] hover:bg-[rgba(167,139,250,0.04)] transition-colors">
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <><ChevronLeft className="w-3 h-3" /><span>收起</span></>}
        </button>
        <button onClick={handleLogout} className="flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-[#5c5470] hover:text-[#f87171] hover:bg-[rgba(248,113,113,0.06)] transition-colors">
          {collapsed ? <LogOut className="w-3 h-3" /> : <><LogOut className="w-3 h-3" /><span>退出</span></>}
        </button>
      </div>
    </aside>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DataProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto relative">
          <div className="fixed inset-0 pointer-events-none opacity-25" style={{
            background: `radial-gradient(ellipse 40% 30% at 10% 80%, rgba(167,139,250,0.04), transparent), radial-gradient(ellipse 50% 40% at 90% 10%, rgba(56,189,248,0.02), transparent), radial-gradient(ellipse 30% 50% at 50% 50%, rgba(251,191,36,0.015), transparent)`,
          }} />
          <div className="relative z-10">{children}</div>
        </main>
      </div>
    </DataProvider>
  );
}
