import type { ScheduleEvent } from "./types";

type AgendaListProps = {
  events: ScheduleEvent[];
  selectedEventId: string | null;
  onSelectEvent: (id: string) => void;
};

export default function AgendaList({
  events,
  selectedEventId,
  onSelectEvent,
}: AgendaListProps) {
  return (
    <div className="agenda-list">
      {events.length === 0 && <div className="empty-state">尚無行程</div>}
      {events.map((event) => (
        <div
          key={event.id}
          className={`agenda-item ${event.tone}${selectedEventId === event.id ? " selected" : ""}`}
          onClick={() => onSelectEvent(event.id)}
        >
          <div className="agenda-date">
            <span>
              {new Date(event.year, event.month - 1, event.date)
                .toLocaleString("en-US", { weekday: "short" })}
            </span>
            <strong>{event.date}</strong>
          </div>
          <div>
            <h3>{event.title}</h3>
            <p>
              {event.startTime
                ? `${event.startTime}${event.endTime ? ` - ${event.endTime}` : ""}`
                : "All day"}
            </p>
            {event.location && <p className="event-location">{event.location}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
