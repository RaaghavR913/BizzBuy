import React from 'react';
import './AnimatedCheckbox.css';

interface AnimatedCheckboxProps {
  checked: boolean;
  className?: string;
}

export function AnimatedCheckbox({ checked, className = '' }: AnimatedCheckboxProps) {
  return (
    <div className={`ios-checkbox ${className}`}>
      <input type="checkbox" checked={checked} readOnly />
      <div className="checkbox-wrapper">
        <div className="checkbox-bg"></div>
        <svg fill="none" viewBox="0 0 24 24" className="checkbox-icon" stroke="currentColor" strokeWidth="3">
          <path strokeLinecap="round" strokeLinejoin="round" className="check-path" d="M5 13l4 4L19 7"></path>
        </svg>
      </div>
    </div>
  );
}
