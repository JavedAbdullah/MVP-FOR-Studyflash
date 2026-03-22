import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Support Tickets",
  description: "Customer support ticketing MVP",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <div className="mx-auto w-full max-w-4xl px-4 py-8">{children}</div>
        </div>
      </body>
    </html>
  );
}
