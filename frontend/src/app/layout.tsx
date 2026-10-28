import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Temporal Truth Engine — Git Happens",
  description: "Checks claims about Hooly at their date and explains each verdict.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
