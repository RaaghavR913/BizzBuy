'use client';
import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

export function SplitText({ text, className = '', delay = 0.05 }: { text: string; className?: string, delay?: number }) {
  const words = text.split(' ');
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-10%' });
  
  return (
    <div ref={ref} className={`flex flex-wrap gap-x-[0.25em] justify-center ${className}`}>
      {words.map((word, i) => (
        <span key={i} className="overflow-hidden inline-block leading-tight">
          <motion.span
            initial={{ y: '100%', opacity: 0 }}
            animate={isInView ? { y: 0, opacity: 1 } : { y: '100%', opacity: 0 }}
            transition={{
              duration: 0.6,
              ease: [0.16, 1, 0.3, 1], // easeOutExpo
              delay: i * delay,
            }}
            className="inline-block pb-1"
          >
            {word}
          </motion.span>
        </span>
      ))}
    </div>
  );
}
