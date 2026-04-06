'use client';

import React, { useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';

interface TiltedCardProps {
  children: React.ReactNode;
  className?: string;
  imageSrc?: string;
  rotationIntensity?: number;
}

export function TiltedCard({ children, className = '', imageSrc, rotationIntensity = 15 }: TiltedCardProps) {
  const ref = useRef<HTMLDivElement>(null);

  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseXSpring = useSpring(x, { stiffness: 300, damping: 30 });
  const mouseYSpring = useSpring(y, { stiffness: 300, damping: 30 });

  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], [`${rotationIntensity}deg`, `-${rotationIntensity}deg`]);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], [`-${rotationIntensity}deg`, `${rotationIntensity}deg`]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const xPct = mouseX / width - 0.5;
    const yPct = mouseY / height - 0.5;

    x.set(xPct);
    y.set(yPct);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateX,
        rotateY,
        transformStyle: 'preserve-3d',
      }}
      className={`relative rounded-2xl w-full h-full cursor-pointer transition-shadow hover:shadow-[0_0_30px_rgba(255,140,0,0.3)] ${className}`}
    >
      <div
        className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.05] to-transparent z-10 pointer-events-none"
        style={{ transform: 'translateZ(20px)' }}
      />
      {imageSrc && (
        <img
          src={imageSrc}
          alt="Card background"
          className="absolute inset-0 w-full h-full object-cover rounded-2xl opacity-40 mix-blend-overlay pointer-events-none"
        />
      )}
      <div 
        className="relative z-20 w-full h-full bg-surface border border-white/[0.08] hover:border-accent/40 rounded-2xl p-6 transition-colors backdrop-blur-sm"
        style={{ transform: 'translateZ(30px)' }}
      >
        {children}
      </div>
    </motion.div>
  );
}
