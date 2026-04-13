export default function GlobalLoading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-busy="true">
      <div className="space-y-4 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent" aria-hidden="true" />
        <p className="text-sm text-text-secondary">불러오는 중</p>
      </div>
    </div>
  );
}
