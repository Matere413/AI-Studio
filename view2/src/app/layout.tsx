import { ReactNode } from 'react';
import './globals.css';

export const metadata = {
  title: 'I-Studio',
  description: 'Plataforma de Marketing y Publicidad',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
