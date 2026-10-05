import { CONDITION_COLORS, CONDITION_LABELS } from "@/lib/conditions";
import type { Condition } from "@/lib/types";

export function ConditionBadge({ condition }: { condition: Condition }) {
  return (
    <span
      title={CONDITION_LABELS[condition]}
      className="inline-block min-w-[2.25rem] rounded px-1.5 py-0.5 text-center text-[11px] font-bold leading-4 text-[#0b0f16]"
      style={{ backgroundColor: CONDITION_COLORS[condition] }}
    >
      {condition}
    </span>
  );
}
