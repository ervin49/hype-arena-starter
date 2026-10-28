import type { Metadata } from "next";
import "@fontsource/poppins/400.css";
import "@fontsource/poppins/500.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";
import "./globals.css";
import { RunProvider } from "@/components/run/RunProvider";

export const metadata: Metadata = {
  title: "Temporal Truth Engine — Git Happens",
  description: "Checks each sentence against what the Hooly universe said on its date.",
};

// Light (blue on white) by default; dark only when chosen with the sidebar toggle.
// Runs before first paint so a saved dark theme does not flash.
const THEME_SCRIPT = `try{if(localStorage.getItem("theme")==="dark")document.documentElement.classList.add("dark")}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="font-sans antialiased">
        <RunProvider>{children}</RunProvider>
      </body>
    </html>
  );
}
