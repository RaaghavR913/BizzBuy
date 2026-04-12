'use client';

export function ShinyText({ text, className = '' }: { text: string; className?: string }) {
  return (
    <span
      className={`inline-block text-transparent bg-clip-text ${className}`}
      style={{
        backgroundImage: 'linear-gradient(110deg,#cbd5e1,45%,#ffffff,55%,#cbd5e1)',
        backgroundSize: '200% 100%',
        animation: 'shine 4s linear infinite',
      }}
    >
      {text}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes shine {
          0% { background-position: 200% 50%; }
          100% { background-position: -200% 50%; }
        }
      `}} />
    </span>
  );
}
