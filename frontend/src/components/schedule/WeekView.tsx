import type { ScheduleEvent } from "./types";
import { weekdays } from "./scheduleUtils";

type WeekViewProps = {
  year: number;
  month: number;
  date: number;
  eventsForDay: (day: number) => ScheduleEvent[];
  isToday: (day: number) => boolean;
  onSelectDay: (day: number) => void;
  onSelectEvent: (id: string) => void;
};

export default function WeekView({
  year,
  month,
  date,
  eventsForDay,
  isToday,
  onSelectDay,
  onSelectEvent,
}: WeekViewProps) {
  // 取得當前日期所在週的星期日起始日
  const currentDateObj = new Date(year, month - 1, date);
  const startOfWeek = new Date(currentDateObj);
  startOfWeek.setDate(currentDateObj.getDate() - currentDateObj.getDay());

  // 建立週的 7 天
  const weekDays: { day: number; month: number }[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    weekDays.push({
      day: d.getDate(),
      month: d.getMonth() + 1,
    });
  }

  return (
    <div className="calendar-card">
      <div className="calendar-weekdays">
        {weekdays.map((day) => <div key={day}>{day}</div>)}
      </div>
      <div className="calendar-grid week-grid">
        {weekDays.map(({ day, month: m }, index) => {
          const dayEvents = eventsForDay(day);
          const isCurrentMonth = m === month;
          return (
            <div
              key={index}
              className={`calendar-cell${isToday(day) ? " today" : ""}${!isCurrentMonth ? " muted" : ""}`}
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