'use client';

export function FluidBackground() {
  return (
    <div className="fixed inset-0 min-h-screen z-0 overflow-hidden bg-black">
      {/* Geometric Gold Background */}
      <div
        className="absolute inset-0 z-0 opacity-40 bg-[url('/bg-gold.png')] bg-cover bg-center bg-no-repeat fixed"
      />
    </div>
  );
}
