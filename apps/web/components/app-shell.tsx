"use client";

import Link from "next/link";
import { PropsWithChildren, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { apiFetch, clearSession, readSession } from "@/lib/api";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/users", label: "Users" },
  { href: "/people", label: "People" },
  { href: "/enrollments", label: "Enrollments" },
  { href: "/sessions", label: "Sessions" },
  { href: "/attendance", label: "Live Attendance" },
  { href: "/logs", label: "Logs" },
  { href: "/review", label: "Review Queue" },
  { href: "/settings", label: "Settings" },
  { href: "/diagnostics", label: "Diagnostics" },
];

type CurrentUser = {
  full_name: string;
  role: string;
};

export function AppShell({ children, title }: PropsWithChildren<{ title: string }>) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    const session = readSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    apiFetch<CurrentUser>("/auth/me", { token: session.accessToken })
      .then(setUser)
      .catch(() => {
        clearSession();
        router.replace("/login");
      });
  }, [router]);

  return (
    <div className="shell-grid">
      <aside className="border-r border-ink/10 bg-white/70 p-6 backdrop-blur">
        <div className="mb-10">
          <p className="pill">Face Attendance</p>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">Admin Console</h1>
          <p className="mt-2 text-sm text-ink/60">
            Liveness reduces spoofing risk. It does not guarantee spoof prevention.
          </p>
        </div>
        <nav className="space-y-2">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-2xl px-4 py-3 text-sm font-medium transition ${
                  active ? "bg-ink text-white" : "text-ink/75 hover:bg-sand"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-10 rounded-2xl bg-sand p-4 text-sm text-ink/75">
          <p className="font-semibold">{user?.full_name ?? "Loading..."}</p>
          <p className="uppercase tracking-[0.18em] text-xs text-ink/50">{user?.role ?? ""}</p>
          <button
            className="btn-secondary mt-4 w-full"
            onClick={() => {
              clearSession();
              router.push("/login");
            }}
          >
            Sign Out
          </button>
        </div>
      </aside>
      <main className="p-6 md:p-10">
        <div className="mb-8">
          <p className="pill">V1</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-tight">{title}</h2>
        </div>
        {children}
      </main>
    </div>
  );
}
