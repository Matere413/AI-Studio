import type { Metadata } from "next";
import "./globals.css";

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
        {children}
      </body>
    </html>
  );
}
