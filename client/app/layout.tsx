import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "TrustGate",
  description: "AI-powered vendor fraud prevention for Squad compliance teams.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: "#0B3142",
              color: "#FFFFFF",
              borderRadius: "8px",
              fontSize: "13px",
              padding: "12px 16px",
            },
            success: {
              iconTheme: { primary: "#0D9B68", secondary: "#FFFFFF" },
            },
            error: {
              iconTheme: { primary: "#DC2626", secondary: "#FFFFFF" },
            },
          }}
        />
      </body>
    </html>
  );
}
