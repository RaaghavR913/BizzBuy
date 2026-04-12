'use client';

export function FluidBackground() {
  return (
    <div className="fixed inset-0 min-h-screen z-[-1] overflow-hidden bg-black">
      {/* Ember Glow Background */}
      <div
        className="absolute inset-0 z-0 opacity-70"
        style={{
          backgroundImage: `
            radial-gradient(circle at 50% 100%, rgba(255, 69, 0, 0.6) 0%, transparent 60%),
            radial-gradient(circle at 50% 100%, rgba(255, 140, 0, 0.4) 0%, transparent 70%),
            radial-gradient(circle at 50% 100%, rgba(255, 215, 0, 0.3) 0%, transparent 80%)
          `,
        }}
      />
    </div>
  );
}
