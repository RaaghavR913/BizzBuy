import React from 'react';
import './loader.css';

export function Loader({ text = "Loading" }: { text?: string }) {
  const chars = text.split("");
  return (
    <div className="loader-wrapper group">
      <div className="loader"></div>
      <div className="flex gap-[0.5px]">
        {chars.map((char, index) => (
          <span 
            key={index} 
            className="loader-letter shadow-black drop-shadow-md" 
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            {char === " " ? "\u00A0" : char}
          </span>
        ))}
      </div>
    </div>
  );
}
