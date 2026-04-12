'use client';
import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

export function BlurText({ text, className = '', delay = 0.05 }: { text: string; className?: string, delay?: number }) {
  const words = text.split(' ');
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-10%' });

  return (
    <div ref={ref} className={`flex flex-wrap gap-x-[0.25em] justify-center ${className}`}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          initial={{ filter: 'blur(10px)', opacity: 0, y: 10 }}
          animate={isInView ? { filter: 'blur(0px)', opacity: 1, y: 0 } : {}}
          transition={{
            duration: 0.8,
            ease: "easeOut",
            delay: i * delay,
          }}
          className="inline-block"
        >
          {word}
        </motion.span>
      ))}
    </div>
  );
}
