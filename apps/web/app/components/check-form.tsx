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
    <form onSubmit={onSubmit} className="mt-8 max-w-3xl space-y-6">
      <label
        className="block font-mono text-[11px] uppercase tracking-[0.16em] text-muted"
        htmlFor="model-id"
      >
        Hugging Face model id
        <input
          id="model-id"
          value={modelId}
          onChange={(event) => setModelId(event.target.value)}
          placeholder="owner/model"
          className="mt-2 block w-full min-w-0 border-b-2 border-text/70 bg-transparent py-1 font-mono text-lg normal-case tracking-normal text-text placeholder:text-text/35 focus:border-text focus:outline-none md:text-xl"
        />
      </label>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <span className="font-mono text-xs text-muted">or try</span>
        {EXAMPLES.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setModelId(id);
              go(id);
            }}
            className="break-all text-left font-mono text-xs text-muted underline decoration-white/25 underline-offset-4 hover:text-text"
          >
            {id}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4 font-mono text-xs uppercase tracking-[0.12em] text-muted">
        <label className="inline-flex items-baseline gap-2">
          HQ
          <select
            value={hq}
            onChange={(event) => setHq(event.target.value)}
            className="border-b-2 border-text/70 bg-transparent font-mono text-base [&_option]:bg-bg normal-case tracking-normal text-text focus:border-text focus:outline-none"
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
            className="accent-[var(--color-paper)]"
          />
          Commercial product
        </label>
      </div>
      <button
        type="submit"
        className="rounded-sm bg-paper px-4 py-2 font-medium text-ink hover:bg-white"
      >
        Check
      </button>
    </form>
  );
}
