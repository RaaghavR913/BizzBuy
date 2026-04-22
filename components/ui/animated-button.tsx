'use client';

import React from 'react';
import Link from 'next/link';
import './animated-button.css';


// Left-pointing arrow path (mirrored)
const LEFT_ARROW = 'M7.82843 10.9999L13.1924 5.63589L11.7782 4.22168L4 11.9999L11.7782 19.778L13.1924 18.3638L7.82843 12.9999H20V10.9999H7.82843Z';
// Right-pointing arrow path
const RIGHT_ARROW = 'M16.1716 10.9999L10.8076 5.63589L12.2218 4.22168L20 11.9999L12.2218 19.778L10.8076 18.3638L16.1716 12.9999H4V10.9999H16.1716Z';

interface AnimatedButtonProps {
  href?: string;
  text: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  variant?: 'gold' | 'emerald' | 'danger';
  direction?: 'forward' | 'back';
}

export function AnimatedButton({ href, text, onClick, disabled, className = '', variant = 'gold', direction = 'forward' }: AnimatedButtonProps) {
  const arrowPath = direction === 'back' ? LEFT_ARROW : RIGHT_ARROW;

  const content = (
    <>
      <svg viewBox="0 0 24 24" className="arr-2" xmlns="http://www.w3.org/2000/svg">
        <path d={arrowPath} />
      </svg>
      <span className="text">{text}</span>
      <span className="circle" />
      <svg viewBox="0 0 24 24" className="arr-1" xmlns="http://www.w3.org/2000/svg">
        <path d={arrowPath} />
      </svg>
    </>
  );

  const baseClassName = `animated-button variant-${variant} ${disabled ? 'opacity-50 cursor-not-allowed pointer-events-none grayscale' : ''} ${className}`;

  if (href) {
    return (
      <Link href={href} className={baseClassName}>
        {content}
      </Link>
    );
  }

  return (
    <button onClick={onClick} disabled={disabled} className={baseClassName} type="button">
      {content}
    </button>
  );
}
