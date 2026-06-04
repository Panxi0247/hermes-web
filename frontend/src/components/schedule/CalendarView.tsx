import type { ScheduleEvent } from "./types";
import { weekdays } from "./scheduleUtils";

type CalendarViewProps = {
  calendarDays: (number | null)[];
  eventsForDay: (day: number) => ScheduleEvent[];
  isToday: (day: number) => boolean;
  onSelectDay: (day: number) => void;
  onSelectEvent: (id: string) => void;
};

export default function CalendarView({
  calendarDays,
  eventsForDay,
  isToday,
  onSelectDay,
  onSelectEvent,
}: CalendarViewProps) {
  return (
    <div className="calendar-card">
      <div className="calendar-weekdays">
        {weekdays.map((day) => <div key={day}>{day}</div>)}
      </div>
      <div className="calendar-grid">
        {calendarDays.map((day, index) => {
          if (!day) return <div key={index} className="calendar-cell muted" />;

          const dayEvents = eventsForDay(day);
          return (
            <div
              key={index}
              className={`calendar-cell${isToday(day) ? " today" : ""}`}
              onClick={() => onSelectDay(day)}
            >
              <div className="day-number">{day}</div>
              <div className="day-events">
                {dayEvents.slice(0, 3).map((event) => (
                  <div
                    key={event.id}
                    className={`mini-event ${event.tone}`}
                    onClick={(clickEvent) => {
                      clickEvent.stopPropagation();
                      onSelectEvent(event.id);
                    }}
                  >
                    <strong>{event.title}</strong>
                    {event.startTime && <span>{event.startTime}</span>}
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className="more-events">+{dayEvents.length - 3}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
