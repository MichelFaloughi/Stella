export interface CalendarEvent {
  title: string;
  startTime: string;
  endTime: string;
  location?: string;
  calendarUrl: string;
}

function LocationIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

export function EventCard({ event }: { event: CalendarEvent }) {
  const { title, startTime, endTime, location, calendarUrl } = event;

  return (
    <article
      className="rounded-xl border border-gray-700 bg-gray-800/80 p-4 shadow-sm backdrop-blur-sm transition-colors hover:border-gray-600"
      data-event-card
    >
      <h3 className="text-base font-semibold text-gray-100 mb-3 leading-tight">
        {title}
      </h3>
      <p className="text-sm text-gray-400 mb-2">
        <span className="text-gray-300">{startTime}</span>
        {endTime ? (
          <>
            <span className="text-gray-500 mx-1.5">–</span>
            <span className="text-gray-300">{endTime}</span>
          </>
        ) : null}
      </p>
      {location ? (
        <p className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <LocationIcon className="flex-shrink-0 text-gray-500" />
          <span>{location}</span>
        </p>
      ) : (
        <div className="mb-4" />
      )}
      <a
        href={calendarUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center rounded-lg bg-gray-700 px-3 py-2 text-sm font-medium text-gray-200 hover:bg-gray-600 hover:text-white transition-colors border border-gray-600 hover:border-gray-500"
      >
        Open in Google Calendar
      </a>
    </article>
  );
}
