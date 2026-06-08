// Color + emoji for each MELD emotion label — used for the chips.
export const EMOTION_STYLE: Record<string, { chip: string; dot: string; emoji: string }> = {
  joy:      { chip: "bg-amber-500/15 text-amber-300 border-amber-500/30",   dot: "bg-amber-400",   emoji: "😄" },
  anger:    { chip: "bg-red-500/15 text-red-300 border-red-500/30",         dot: "bg-red-400",     emoji: "😠" },
  sadness:  { chip: "bg-sky-500/15 text-sky-300 border-sky-500/30",         dot: "bg-sky-400",     emoji: "😢" },
  surprise: { chip: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30", dot: "bg-fuchsia-400", emoji: "😲" },
  fear:     { chip: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30", dot: "bg-indigo-400",  emoji: "😨" },
  disgust:  { chip: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", dot: "bg-emerald-400", emoji: "🤢" },
  neutral:  { chip: "bg-slate-500/15 text-slate-300 border-slate-500/30",   dot: "bg-slate-400",   emoji: "😐" },
};

export function emotionStyle(e: string) {
  return EMOTION_STYLE[e] ?? EMOTION_STYLE.neutral;
}
