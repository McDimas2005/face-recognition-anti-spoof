export function StatCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string | number;
  description: string;
}) {
  return (
    <div className="glass-card p-6">
      <p className="text-sm uppercase tracking-[0.18em] text-ink/45">{label}</p>
      <p className="mt-3 text-4xl font-semibold">{value}</p>
      <p className="mt-3 text-sm text-ink/65">{description}</p>
    </div>
  );
}

