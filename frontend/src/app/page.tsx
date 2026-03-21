"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { CountryListItem } from "@/lib/types";
import { formatPct, changeColor } from "@/lib/utils";

export default function HomePage() {
  const [countries, setCountries] = useState<CountryListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getCountries().then(setCountries).catch(console.error).finally(() => setLoading(false));
  }, []);

  const flags: Record<string, string> = { US: "🇺🇸", KR: "🇰🇷", JP: "🇯🇵" };

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Predict</h1>
        <p className="text-text-secondary mt-1">AI-powered market analysis for US, KR, JP</p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse h-48" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {countries.map((c) => (
            <Link
              key={c.code}
              href={`/country/${c.code}`}
              className="card hover:border-accent/50 transition-colors group"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{flags[c.code]}</span>
                <div>
                  <h2 className="font-semibold text-lg group-hover:text-accent transition-colors">
                    {c.name_local}
                  </h2>
                  <span className="text-xs text-text-secondary">{c.name}</span>
                </div>
              </div>

              <div className="space-y-2">
                {c.indices.map((idx) => (
                  <div key={idx.ticker} className="flex justify-between items-baseline">
                    <span className="text-sm text-text-secondary">{idx.name}</span>
                    <div className="text-right">
                      <span className="font-mono text-sm">{idx.price.toLocaleString()}</span>
                      <span className={`ml-2 text-sm font-medium ${changeColor(idx.change_pct)}`}>
                        {formatPct(idx.change_pct)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
