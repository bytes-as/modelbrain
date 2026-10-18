"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

const EXAMPLES = [
  "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
  "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8",
  "grimjim/llama-3-Nephilim-v1-8B",
  "Qwen/Qwen2.5-7B-Instruct",
];

export function CheckForm() {
  const router = useRouter();
  const [modelId, setModelId] = useState(EXAMPLES[0]);
  const [hq, setHq] = useState("DE");
  const [commercial, setCommercial] = useState(true);

  function go(id: string) {
    const [owner, name] = id.split("/");
    if (!owner || !name) return;
    const params = new URLSearchParams({
      hq,
      c: commercial ? "1" : "0",
    });
    router.push(`/m/${owner}/${name}?${params.toString()}`);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    go(modelId.trim());
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 max-w-3xl space-y-4">
      <label className="block text-sm text-muted" htmlFor="model-id">
        Hugging Face model id
        <input
          id="model-id"
          value={modelId}
          onChange={(event) => setModelId(event.target.value)}
          placeholder="owner/model"
          className="mt-2 w-full rounded border border-white/10 bg-surface px-3 py-3 font-mono text-text"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setModelId(id);
              go(id);
            }}
            className="rounded-full border border-white/10 px-3 py-1 text-left font-mono text-xs text-muted hover:text-accent"
          >
            {id}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <label>
          HQ
          <select
            value={hq}
            onChange={(event) => setHq(event.target.value)}
            className="ml-2 rounded border border-white/10 bg-surface px-2 py-1"
          >
            <option value="DE">Germany</option>
            <option value="FR">France</option>
            <option value="US">United States</option>
          </select>
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={commercial}
            onChange={(event) => setCommercial(event.target.checked)}
          />
          Commercial product
        </label>
      </div>
      <button type="submit" className="rounded bg-accent px-4 py-2 font-medium text-bg">
        Check
      </button>
    </form>
  );
}
