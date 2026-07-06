import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/features/auth/application/auth-provider";

export const metadata: Metadata = {
  title: "I-Studio",
  description: "AI creative workspace",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-base text-primary font-body text-base antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
