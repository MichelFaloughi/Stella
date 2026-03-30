export interface Email {
  subject: string;
  from: string;
  snippet?: string;
  date?: string;
  labels?: string[];
  messageId: string;
}

const LABEL_DISPLAY: Record<string, { text: string; className: string }> = {
  UNREAD: { text: "Unread", className: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
  IMPORTANT: { text: "Important", className: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
  STARRED: { text: "Starred", className: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

function formatFrom(from?: string): string {
  if (!from) return "";
  const match = from.match(/^"?([^"<]+?)"?\s*</);
  if (match) return match[1].trim();
  return from;
}

export function EmailCard({ email }: { email: Email }) {
  const { subject, from, snippet, date, labels, messageId } = email;
  const gmailUrl = `https://mail.google.com/mail/u/0/#all/${messageId}`;
  const isUnread = labels?.includes("UNREAD");
  const displayLabels = (labels ?? []).filter((l) => l in LABEL_DISPLAY);

  return (
    <article
      className="rounded-xl border border-gray-700 bg-gray-800/80 p-4 shadow-sm backdrop-blur-sm transition-colors hover:border-gray-600"
      data-email-card
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3
          className={`text-base leading-tight ${
            isUnread ? "font-semibold text-gray-100" : "font-medium text-gray-300"
          }`}
        >
          {subject || "(No subject)"}
        </h3>
        {date && (
          <span className="text-xs text-gray-500 flex-shrink-0">{formatDate(date)}</span>
        )}
      </div>

      <p className="text-sm text-gray-400 mb-2">{formatFrom(from)}</p>

      {snippet && (
        <p className="text-sm text-gray-500 mb-3 line-clamp-2 leading-relaxed">{snippet}</p>
      )}

      {displayLabels.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {displayLabels.map((label) => {
            const config = LABEL_DISPLAY[label];
            return (
              <span
                key={label}
                className={`text-xs px-2 py-0.5 rounded-full border ${config.className}`}
              >
                {config.text}
              </span>
            );
          })}
        </div>
      )}

      <a
        href={gmailUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center rounded-lg bg-gray-700 px-3 py-2 text-sm font-medium text-gray-200 hover:bg-gray-600 hover:text-white transition-colors border border-gray-600 hover:border-gray-500"
      >
        Open in Gmail
      </a>
    </article>
  );
}
